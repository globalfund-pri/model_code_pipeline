import os
import pathlib
from string import ascii_lowercase

import numpy as np
import pandas as pd
import pytest
from code_and_data_for_tests.funcs_for_test import (
    GpTestData,
    ModelResultsTestData,
    PartnerDataTest,
    PFInputDataTest,
)
from matplotlib import pyplot as plt

from tgftools.analysis import Analysis
from tgftools.approach_b import (
    ApproachB,
    ApproachBDataSet,
    ApproachBResult,
    get_dummy_country_result,
)
from tgftools.database import Database
from tgftools.filehandler import NonTgfFunding, Parameters, TgfFunding
from tgftools.utils import open_file

"""Tests related to the classes for accomplishing Approach B."""

path_to_data_for_tests = (
    pathlib.Path(os.path.dirname(__file__)) / "code_and_data_for_tests"
)

PLT_SHOW = False

@pytest.fixture
def database():
    """Return a database with Test data."""
    return Database(
        model_results=ModelResultsTestData(
            path_to_data_for_tests / "model_results.csv"
        ),
        gp=GpTestData(
            fixed_gp=path_to_data_for_tests / "gp.csv",
            model_results=None,
            partner_data=None,
        ),
        partner_data=PartnerDataTest(path_to_data_for_tests / "partner_data.csv"),
        pf_input_data=PFInputDataTest(path_to_data_for_tests / "pf.csv"),
    )


@pytest.fixture
def analysis(database):
    return Analysis(
        database=database,
        tgf_funding=TgfFunding(path_to_data_for_tests / "tgf_funding.csv"),
        non_tgf_funding=NonTgfFunding(path_to_data_for_tests / "non_tgf_funding.csv"),
        parameters=Parameters(path_to_data_for_tests / "parameters.toml"),
    )


def test_approach_b_direct_access(analysis, tmp_path):
    """Check the functions on `ApproachB`, picking up the object from the analysis class (which creates the appropriate
    data structures needed)."""

    approach_b = analysis._approach_b()

    # Inspect the pre-processed model results
    filename = tmp_path / 'inspect_model_results.pdf'
    approach_b.inspect_model_results(plt_show=PLT_SHOW, filename=filename)
    # open_file(filename)

    # Run using all optimisation approaches & plot summary graphs about it.
    results = approach_b.run(
        methods=None, provide_best_only=True  # None implies that all methods are used
    )
    approach_b.plot_approach_b_results(results, plt_show=PLT_SHOW)

    # Run using only the Greedy Algorithm going backwards: should get one 'ApproachBResult' object
    assert isinstance(
        approach_b.do_approach_b(methods=["ga_backwards"], provide_best_only=True),
        ApproachBResult,
    )

    # Run all and get separate results for each
    all_results = approach_b.do_approach_b(methods=None, provide_best_only=False)
    assert isinstance(all_results, tuple)
    assert isinstance(all_results[0], dict)
    assert all([isinstance(v, ApproachBResult) for v in all_results[0].values()])
    assert isinstance(all_results[1], str)
    assert all_results[1] in all_results[0]


def test_force_monotonic(analysis):
    """Check that the option `force_monotonic_decreasing` option in ApproachB works."""

    # Make results _not_ monotonically decreasing by scrambling the data
    df = analysis.database.model_results.df
    df.index = df.index[np.random.permutation(len(df.index))]
    analysis.database.model_results.df = df.sort_index()

    # Construct data-frame WITHOUT `force_monotonic_decreasing`
    analysis.parameters.int_store['FORCE_MONOTONIC_DECREASING'] = False
    data_frames_for_approach_b = analysis.get_data_frames_for_approach_b()

    # Check that not monotonic when not using the option
    with pytest.warns(UserWarning) as record:
        db = ApproachBDataSet(
            model_results=data_frames_for_approach_b["model_results"],
        )
    for _c in db.countries:
        assert not (
            db.data[_c].results.cases.is_monotonic_decreasing
            and db.data[_c].results.deaths.is_monotonic_decreasing
        )

    # Re-build the dataframes WITH force_monotonic_decreasing` and check they cases and deaths are now monotonically
    # decreasing with cases and deaths
    analysis.parameters.int_store['FORCE_MONOTONIC_DECREASING'] = True
    data_frames_for_approach_b_with_forcing = analysis.get_data_frames_for_approach_b()

    db = ApproachBDataSet(
        model_results=data_frames_for_approach_b_with_forcing["model_results"],
    )
    for _c in db.countries:
        assert (
            db.data[_c].results.cases.is_monotonic_decreasing
            and db.data[_c].results.deaths.is_monotonic_decreasing
        )


def test_dummy_country_profile():
    """Examine the country results that are created."""
    if PLT_SHOW:
        np.random.seed(2)  # <-- use to control the seed if needed

        fig, ax = plt.subplots(2, 1, sharex=True)

        for _ in range(10):
            res, gp = get_dummy_country_result()
            ax[0].plot(res.index, res.cases)
            ax[0].plot(gp.cost, gp.cases, "k*")
            ax[1].plot(res.index, res.deaths)
            ax[1].plot(gp.cost, gp.deaths, "k*")

        ax[0].set_ylabel("Cases")
        ax[1].set_ylabel("Deaths")
        ax[1].set_xlabel("Cost")
        fig.suptitle("Example of Country Results Curves")
        fig.show()
        plt.close(fig)


def test_optimisation_using_dummy_country_profiles(tmp_path):
    """Check optimisation results using dummy country data."""
    num_dummy_countries = 5  # (fewer is quicker!; max 26)

    rng = np.random.default_rng(seed=1)

    model_results = []
    min_costs = {}
    max_costs = {}

    def format_dict_into_df(d):
        return (
            pd.DataFrame.from_dict(d, orient="index")
            .reset_index()
            .rename(columns={"index": "country", 0: "value"})
        )

    # Build dataframes needed for approach B
    for country in ascii_lowercase[0: min(26, num_dummy_countries)]:
        res, _ = get_dummy_country_result(rng)
        res = res.reset_index()
        res = res.rename(columns={"0": "cost"})
        res["country"] = country
        model_results.append(res)
        min_costs[country] = res.cost.min()
        max_costs[country] = res.cost.max()

    # model results composed of randomly drawn country profiles:
    model_results = pd.concat(model_results, axis=0)

    # non_tgf funding is some random fraction of the total costs:
    non_tgf_funding = {
        country: its_max * rng.random() for country, its_max in max_costs.items()
    }

    # tgf_funding is some proportion of the unmet net:
    tgf_funding = {
        country: (max_costs[country] - non_tgf) * rng.random() * 0.25
        for country, non_tgf in non_tgf_funding.items()
    }

    assert ((pd.Series(non_tgf_funding) / pd.Series(max_costs)) < 1.0).all()
    assert (
        (((pd.Series(tgf_funding) + pd.Series(non_tgf_funding)) / pd.Series(max_costs)))
        < 1.0
    ).all()

    # Approach B:
    # - create the object
    approach_b = ApproachB(
        model_results=model_results,
        non_tgf_budgets=format_dict_into_df(non_tgf_funding),
        tgf_budgets=format_dict_into_df(tgf_funding),
    )
    # - inspect results
    approach_b.inspect_model_results(plt_show=PLT_SHOW)


    # - do the optimisation using all methods (and produce report)
    filename = tmp_path / 'report_from_approach_b.pdf'
    all_results = approach_b.run(
        methods=None,
        provide_best_only=False,
        filename=filename,
    )
    # open_file(tmp_path / 'report_from_approach_b.pdf')

    # - compare results
    b_methods = all_results["b"][0]

    tgf_funding_allox = pd.DataFrame(
        {method: result.tgf_budget_by_country for method, result in b_methods.items()}
    )
    tgf_funding_allox.plot()
    if PLT_SHOW:
        plt.show()

    overall_impact = pd.DataFrame(
        {
            method: (result.total_result.deaths, result.total_result.cases)
            for method, result in b_methods.items()
        },
    ).T.rename(columns={0: "deaths", 1: "cases"})
    overall_impact.T.plot.bar()
    plt.tight_layout()
    if PLT_SHOW:
        plt.show()

    # - plot favoured results
    best_result = {"a": all_results["a"], "b": all_results["b"][0][all_results["b"][1]]}
    approach_b.plot_approach_b_results(best_result, plt_show=PLT_SHOW)


def test_optimisation_using_dummy_country_profiles_when_tgf_funding_is_large(tmp_path):
    """Check optimisation results using dummy country data, when the TGF Funding is large and is more than enough
    for every country to be fully funded."""
    plt_show = False
    num_dummy_countries = 5  # (fewer is quicker!; max 26)

    rng = np.random.default_rng(seed=1)

    model_results = []
    min_costs = {}
    max_costs = {}

    def format_dict_into_df(d):
        return (
            pd.DataFrame.from_dict(d, orient="index")
            .reset_index()
            .rename(columns={"index": "country", 0: "value"})
        )

    # Build dataframes needed for approach B
    for country in ascii_lowercase[0: min(26, num_dummy_countries)]:
        res, _ = get_dummy_country_result(rng)
        res = res.reset_index()
        res = res.rename(columns={"0": "cost"})
        res["country"] = country
        model_results.append(res)
        min_costs[country] = res.cost.min()
        max_costs[country] = res.cost.max()

    # model results composed of randomly drawn country profiles:
    model_results = pd.concat(model_results, axis=0)

    # non_tgf funding is some random fraction of the total costs:
    non_tgf_funding = {
        country: its_max * rng.random() for country, its_max in max_costs.items()
    }

    # tgf_funding is GREATER than the unmet net:
    tgf_funding = {
        country: (max_costs[country] - non_tgf) * 1.25
        for country, non_tgf in non_tgf_funding.items()
    }

    assert (((pd.Series(tgf_funding) + pd.Series(non_tgf_funding)) / pd.Series(max_costs)) >= 1.0).all()

    # Approach B:
    # - create the object
    approach_b = ApproachB(
        model_results=model_results,
        non_tgf_budgets=format_dict_into_df(non_tgf_funding),
        tgf_budgets=format_dict_into_df(tgf_funding),
    )
    # - inspect results
    approach_b.inspect_model_results(plt_show=plt_show)

    # - do the optimisation using all methods
    all_results = approach_b.run(
        methods=['ga_backwards', 'ga_forwards'],  # todo with other methods this becomes very slow
        provide_best_only=False,
    )

    # - All results should be the same, and equal to fully funding every country
    solutions = all_results['b'][0]

    assert np.allclose(
        np.array(list(solutions['ga: forwards'].tgf_budget_by_country.values())),
        np.array(list(solutions['ga: backwards'].tgf_budget_by_country.values())),
        rtol=0.01
    )

    assert np.allclose(
        np.array(list(solutions['ga: forwards'].total_budget_by_country.values())),
        np.array(list(solutions['ga: backwards'].total_budget_by_country.values())),
        rtol=0.001
    )

    assert np.allclose(
        np.array(list(solutions['ga: backwards'].total_budget_by_country.values())),
        np.array(list(max_costs.values())),
        rtol=0.001
    )

    assert np.allclose(
        np.array([
            solutions['ga: forwards'].total_result.cases,
            solutions['ga: forwards'].total_result.deaths,
            solutions['ga: forwards'].total_result.cost]),
        np.array([
            solutions['ga: backwards'].total_result.cases,
            solutions['ga: backwards'].total_result.deaths,
            solutions['ga: backwards'].total_result.cost]),
        rtol=0.001
    )
