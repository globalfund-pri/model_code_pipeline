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
        tgf_funding=TgfFunding(path_to_data_for_tests / "tgf_funding.csv"),
        non_tgf_funding=NonTgfFunding(path_to_data_for_tests / "non_tgf_funding.csv"),
        parameters=Parameters(path_to_data_for_tests / "parameters.toml")
    )


def test_analysis_approach_a(analysis):
    rtn = analysis.portfolio_projection_approach_a()
    assert isinstance(rtn, PortfolioProjection)


def test_analysis_approach_b(analysis):
    rtn = analysis.portfolio_projection_approach_b()
    assert isinstance(rtn, PortfolioProjection)

def test_analysis_diagnostic_report(analysis, tmp_path):
    """Test that we can run the diagnostic report that compares approach A and B and shows the cost-impact curves"""
    filename_for_report = tmp_path / "diagnostic_report.pdf"

    analysis.make_diagnostic_report(
        filename=filename_for_report,
        plt_show=False,
    )
    assert os.path.exists(filename_for_report)
    # open_file(filename_for_report)


def test_analysis_portfolio_projection_counterfactual(analysis):
    rtn = analysis.portfolio_projection_counterfactual('cf_null')
    assert isinstance(rtn, PortfolioProjection)


def test_dump_to_excel(analysis, tmp_path):
    tmp_file = tmp_path / 'analysis.xlsx'
    analysis.dump_everything_to_xlsx(tmp_file)
    # open_file(tmp_file)
