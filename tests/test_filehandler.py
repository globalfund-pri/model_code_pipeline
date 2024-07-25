import os
import pathlib

import pandas as pd
import pytest
from code_and_data_for_tests.funcs_for_test import (
    GpTestData,
    ModelResultsTestData,
    PartnerDataTest,
    PFInputDataTest,
)

from tgftools.filehandler import (
    CalibrationData,
    Datum,
    NonTgfFunding,
    Parameters,
    TgfFunding,
    FileHandler,
)
from tgftools.utils import get_root_path

path_to_data_for_tests = (
    pathlib.Path(os.path.dirname(__file__)) / "code_and_data_for_tests"
)


@pytest.fixture
def gp():
    return GpTestData(
        fixed_gp=path_to_data_for_tests / "gp.csv",
        model_results=None,
        partner_data=None,
    )

@pytest.fixture
def parameters():
    return Parameters(path_to_data_for_tests / "parameters.toml")


def test_load_model_results(parameters):
    """Should be able to use the ModelResultsTestData filehandler to load results and access them."""
    model_results = ModelResultsTestData(
        path=path_to_data_for_tests / "model_results.csv",
        parameters=parameters,
    )

    # Access the pd.DataFrame directly
    assert isinstance(model_results.df, pd.DataFrame)
    assert {"low", "central", "high"} == set(model_results.df.columns)

    # Attempt to retrieve a value that is present
    assert isinstance(
        model_results.get(
            scenario_descriptor="default",
            funding_fraction=0.8,
            country="A",
            year=2010,
            indicator="deaths",
        ),
        Datum,
    )

    # Attempt to retrieve a value that is not present --> should raise an Exception
    with pytest.raises(KeyError):
        model_results.get(
            scenario_descriptor="default",
            funding_fraction=0.8,
            country="XX",  # <-- not a country in those data
            year=2010,
            indicator="deaths",
        )

    # Access properties
    assert isinstance(model_results.countries, list)
    assert isinstance(model_results.indicators, list)
    assert isinstance(model_results.funding_fractions, list)
    assert isinstance(model_results.scenario_descriptors, list)
    assert isinstance(model_results.counterfactuals, list)




def test_load_gp(gp):
    """Should be able to use the Gp filehandler to load the Global Plan data and access them."""

    # Access the pd.DataFrame directly
    assert isinstance(gp.df, pd.DataFrame)


def test_load_calibration_data():
    """Should be able to use the CalibrationData filehandler to load the external calibration data and access them."""

    calib = CalibrationData(path_to_data_for_tests / "calibration.csv")

    # Access the pd.DataFrame directly
    assert isinstance(calib.df, pd.DataFrame)
    assert {"low", "central", "high"} == set(calib.df.columns)

    # Attempt to retrieve a value that is present
    assert isinstance(calib.get(country="A", year=2010, indicator="deaths"), Datum)

    # Attempt to retrieve a value that is not present --> should raise an Exception
    with pytest.raises(Exception):
        calib.get(
            country="XX",
            year=2010,
            indicator="deaths",  # <-- not a country in those data
        )


def test_load_partner_data():
    """Should be able to use the Partner Data filehandler to load the external calibration data and access them."""

    partner_data = PartnerDataTest(path_to_data_for_tests / "partner_data.csv")

    # Access the pd.DataFrame directly
    assert isinstance(partner_data.df, pd.DataFrame)
    assert {"central"} == set(partner_data.df.columns)

    # Attempt to retrieve a value that is not present --> should raise an Exception
    with pytest.raises(Exception):
        partner_data.get(
            country="XX",
            year=2010,
            indicator="deaths",  # <-- not a country in those data
        )


def test_load_pf_data():
    """Should be able to use the PF Data filehandler to load the external calibration data and access them."""

    pf_data = PFInputDataTest(path_to_data_for_tests / "pf.csv")

    # Access the pd.DataFrame directly
    assert isinstance(pf_data.df, pd.DataFrame)
    assert {"central"} == set(pf_data.df.columns)

    # Attempt to retrieve a value that is not present --> should raise an Exception
    with pytest.raises(Exception):
        pf_data.get(
            country="XX",
            year=2010,
            indicator="deaths",  # <-- not a country in those data
        )


def test_load_tgf_funding_data():
    """Should be able to use the TgfFuning filehandler to load these funding data and access them."""

    target_file = path_to_data_for_tests / "tgf_funding.csv"
    TgfFunding(target_file)


def test_load_non_tgf_funding_data():
    """Should be able to use the NonTgfFuning filehandler to load these funding data and access them."""

    target_file = path_to_data_for_tests / "non_tgf_funding.csv"
    NonTgfFunding(target_file)



def test_parameters():

    parameters_file = get_root_path() / "tests" / "code_and_data_for_tests" / "parameters.toml"
    parameters = Parameters(parameters_file)

    # Retrieve a generic parameter
    assert isinstance(parameters.get("START_YEAR"), int)

    # Get a table of the Scenarios
    scenarios = parameters.get_scenarios()
    assert isinstance(scenarios, pd.Series)
    assert isinstance(scenarios.index.to_list(), list)

    # Get a table of the Counterfactuals
    counterfactuals = parameters.get_counterfactuals()
    assert isinstance(counterfactuals, pd.Series)
    assert ['cf_null'] == counterfactuals.index.to_list()

    # Get a table of the Counterfactual flagged as being "null"
    null_counterfactuals = parameters.get_nullcounterfactuals()
    assert isinstance(null_counterfactuals, pd.Series)  # (blank if not counterfactuals defined)

    # Get a table of the Counterfactual flagged as being "constant coverage"
    cc_counterfactuals = parameters.get_cccounterfactuals()
    assert isinstance(cc_counterfactuals, pd.Series)  # (blank if not counterfactuals defined)

    # Get a list of the countries in the portfolio for diseaseX
    portfolio_countries = parameters.get_portfolio_countries_for('diseaseX')
    assert isinstance(portfolio_countries, list) and (len(portfolio_countries) > 0)

    # Get a list of the countries modelled for diseaseX
    modelled_countries = parameters.get_modelled_countries_for('diseaseX')
    assert isinstance(modelled_countries, list) and (len(modelled_countries) > 0)
    assert set(modelled_countries).issubset(portfolio_countries)

    # Get a table of indicators for diseaseX
    indicators = parameters.get_indicators_for('diseaseX')
    assert isinstance(indicators, pd.DataFrame)
    assert indicators.use_scaling.dtype == 'bool'
    assert len(indicators) > 0


def test_load_from_df():
    """Check that can create a FileHandler-like object directly from passing-in a dataframe."""
    class MyFh(FileHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def _checks(self, _df: pd.DataFrame):
            pass

    my_df = pd.DataFrame({'A': [0, 10, 20, 30], 'B': [0, 1, 2, 3]})
    fh = MyFh.from_df(my_df.copy())
    assert isinstance(fh, MyFh)
    assert my_df.equals(fh.df)
