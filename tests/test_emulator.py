import os
import pathlib

import numpy as np
import pandas as pd
import pytest
from code_and_data_for_tests.funcs_for_test import (
    GpTestData,
    ModelResultsTestData,
    PartnerDataTest,
    PFInputDataTest,
)

from tgftools.database import Database
from tgftools.emulator import Emulator
from tgftools.filehandler import Parameters

path_to_data_for_tests = (
    pathlib.Path(os.path.dirname(__file__)) / "code_and_data_for_tests"
)


@pytest.fixture
def parameters():
    return Parameters(path_to_data_for_tests / "parameters.toml")

@pytest.fixture
def database(parameters):
    return Database(
        model_results=ModelResultsTestData(
            path_to_data_for_tests / "model_results.csv",
            parameters=parameters,
        ),
        gp=GpTestData(
            fixed_gp=path_to_data_for_tests / "gp.csv",
            model_results=None,
            partner_data=None,
        ),
        partner_data=PartnerDataTest(path_to_data_for_tests / "partner_data.csv"),
        pf_input_data=PFInputDataTest(path_to_data_for_tests / "pf.csv"),
    )


def test_emulator(database):
    """The emulator should return results expected from a database with model results that are well-behaved."""

    # Choose some example country/scenario/indicator and get all the funding fractions defined.
    _country = database.model_results.countries[0]
    _scenario_descriptor = database.model_results.scenario_descriptors[0]
    _indicator = database.model_results.indicators[0]
    funding_fractions_in_db = database.model_results.funding_fractions

    _years_for_funding = Parameters(
            path_to_data_for_tests / "parameters.toml"
        ).get("YEARS_FOR_FUNDING")

    # Initiate the Emulator for some particular scenario descriptor
    em = Emulator(
        database=database,
        scenario_descriptor=_scenario_descriptor,
        country=_country,
        years_for_funding=_years_for_funding,
    )

    # Ask for a scenario that corresponds to a funding_fraction that is actually present in the database
    for _funding_fraction in funding_fractions_in_db:
        country_df = em.get(
            funding_fraction=_funding_fraction,
        )

        assert isinstance(country_df, dict)
        assert all([isinstance(_x, pd.DataFrame) for _x in country_df.values()])

        pd.testing.assert_frame_equal(
            country_df[_indicator],
            database.get_country(
                country=_country,
                scenario_descriptor=_scenario_descriptor,
                funding_fraction=_funding_fraction,
                indicator=_indicator,
            ),
        )

    # Ask for a scenario that corresponds to a funding_fraction that are not actually present in the database but
    #  which should be possible to interpolate. Check that it conforms to expectations using the numpy function.
    # We use the statistic of new infections in 2010 in the model central column here, but we could have used anything.

    def em_get_cases_in_2030(_funding_fraction):
        """Wrapper to simplify calling to the emulator and getting the 'new infections' indicator in year 2010 for the
        central model result."""
        return em.get(funding_fraction=_funding_fraction)[_indicator].loc[
            2030, "model_central"
        ]

    ff = np.linspace(funding_fractions_in_db[0], funding_fractions_in_db[-1], 100)

    result_from_emulator = np.array([em_get_cases_in_2030(f) for f in ff])
    result_from_interp = np.interp(
        ff,
        funding_fractions_in_db,
        [
            database.get_country(
                country=_country,
                scenario_descriptor=_scenario_descriptor,
                indicator=_indicator,
                funding_fraction=f,
            ).loc[2030, "model_central"]
            for f in funding_fractions_in_db
        ],
    )
    assert np.allclose(result_from_emulator, result_from_interp)

    # Ask for a scenario that is nonsensical -> an error should be raised
    with pytest.raises(ValueError):
        em_get_cases_in_2030(float("nan"))
    with pytest.raises(ValueError):
        em_get_cases_in_2030(-0.1)
    with pytest.raises(ValueError):
        em_get_cases_in_2030(1.1)

    # Ask for a scenario that cannot be interpolated (past the last data point) -> an error should be raised.
    with pytest.raises(ValueError):
        em_get_cases_in_2030(
            funding_fractions_in_db[0] * 0.99
        )  # below the lowest data point
    with pytest.raises(ValueError):
        em_get_cases_in_2030(
            funding_fractions_in_db[-1] * 1.01
        )  # above the highest data point


def test_ff_to_dollar_and_dollar_to_ff(database):
    """Check the GP FileHandler can correctly compute the funding fraction and dollar amounts for countries."""

    # Choose some example country/scenario/indicator and get all the funding fractions defined.
    _country = database.model_results.countries[0]
    _scenario_descriptor = database.model_results.scenario_descriptors[0]
    _indicator = database.model_results.indicators[0]
    years_for_summing = Parameters(
        path_to_data_for_tests / "parameters.toml"
    ).get("YEARS_FOR_FUNDING")

    # Initiate the Emulator for some particular scenario descriptor
    em = Emulator(
        database=database,
        scenario_descriptor=_scenario_descriptor,
        country=_country,
        years_for_funding=years_for_summing,
    )

    # Compute cost for each funding_fraction and check that these are produced by the Emulator
    ff_to_cost = (
        database.model_results.df.loc[
            (_scenario_descriptor, slice(None), _country, years_for_summing, "cost"),
            "central",
        ]
        .groupby(axis=0, level="funding_fraction")
        .sum()
        .to_dict()
    )

    def total_cost(x: pd.DataFrame) -> float:
        """Returns the total cost from a pd.DataFrame for the indicator cost, which is the sum of the `model_central`
        with in the `years_for_summing`."""
        return x.loc[years_for_summing, "model_central"].sum()

    for ff, expected_cost in ff_to_cost.items():
        # for a given funding_fraction, the cost dataframe should imply the expected cost
        assert np.isclose(
            expected_cost, total_cost(em.get(funding_fraction=ff)["cost"])
        )

        # for a given total dollar cost, the cost dataframe should imply that same expected cost
        assert np.isclose(
            expected_cost, total_cost(em.get(dollars=expected_cost)["cost"])
        )

        # The same set of indicators should be provided, when passing in either a ff or the corresponding dollar amount
        pd.testing.assert_frame_equal(
            em.get(funding_fraction=ff)[_indicator],
            em.get(dollars=expected_cost)[_indicator],
        )

    # Check that conversion from dollar --> funding fraction --> dollar works, for arbitrary dollar amounts
    for dollars in np.linspace(
        np.array(list(ff_to_cost.values())).min(),
        np.array(list(ff_to_cost.values())).max(),
        100,
    ):
        cost_of_full_funding = total_cost(em.get(funding_fraction=1.0)["cost"])
        ff = total_cost(em.get(dollars=dollars)["cost"]) / cost_of_full_funding
        assert np.isclose(dollars, total_cost(em.get(funding_fraction=ff)["cost"]))
