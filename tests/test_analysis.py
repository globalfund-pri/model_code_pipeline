import os
import pathlib

import pytest
from code_and_data_for_tests.funcs_for_test import (
    GpTestData,
    ModelResultsTestData,
    PartnerDataTest,
    PFInputDataTest,
)

from tgftools.analysis import Analysis, PortfolioProjection
from tgftools.database import Database
from tgftools.filehandler import NonTgfFunding, Parameters, TgfFunding
from tgftools.utils import open_file

path_to_data_for_tests = (
    pathlib.Path(os.path.dirname(__file__)) / "code_and_data_for_tests"
)


@pytest.fixture
def database():
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
        scenario_descriptor="default",
        tgf_funding=TgfFunding(path_to_data_for_tests / "tgf_funding.csv"),
        non_tgf_funding=NonTgfFunding(path_to_data_for_tests / "non_tgf_funding.csv"),
        parameters=Parameters(path_to_data_for_tests / "parameters.toml")
    )


def test_analysis_approach_a(analysis):
    rtn = analysis.portfolio_projection_approach_a()
    assert isinstance(rtn, PortfolioProjection)


def test_analysis_approach_b(analysis):
    rtn = analysis.portfolio_projection_approach_b(
        optimisation_params={
            "force_monotonic_decreasing": False,
            "years_for_obj_func": Parameters(
                path_to_data_for_tests / "parameters.toml"
            ).get("YEARS_FOR_OBJ_FUNC"),
        },
        methods=[
            "ga_forwards",
            "ga_backwards",
            "global_start_at_a",
            "global_start_at_random",
            "global_start_at_random",  # <-- repeats so that different random starting points are used
            "global_start_at_random",
            "local_start_at_a",
            "local_start_at_random",
            "local_start_at_random",  # <-- repeats so that different random starting points are used
            "local_start_at_random",
        ],
    )
    assert isinstance(rtn, PortfolioProjection)


def test_analysis_portfolio_projection_counterfactual(analysis):
    rtn = analysis.portfolio_projection_counterfactual('cf_null')
    assert isinstance(rtn, PortfolioProjection)


def test_dump_to_excel(analysis, tmp_path):
    tmp_file = tmp_path / 'analysis.xlsx'
    analysis.dump_everything_to_xlsx(tmp_file)
    # open_file(tmp_file)
