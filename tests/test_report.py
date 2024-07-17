import copy
import os
import pathlib

import pytest
from code_and_data_for_tests.funcs_for_test import (
    GpTestData,
    ModelResultsTestData,
    PartnerDataTest,
    PFInputDataTest, TestReport,
)

from tgftools.analysis import Analysis
from scripts.ic7.shared.htm_report import SetOfPortfolioProjections
from tgftools.database import Database
from tgftools.filehandler import NonTgfFunding, Parameters, TgfFunding
from tgftools.utils import open_file

path_to_data_for_tests = (
    pathlib.Path(os.path.dirname(__file__)) / "code_and_data_for_tests"
)

from tgftools.report import Report


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
        parameters=Parameters(path_to_data_for_tests / "parameters.toml"),
    )


def test_report(tmp_path):
    """Create test report, passing it a dict to substitute for the results that would be used to make the form."""
    report = TestReport(diseaseX={'stat1': 10, 'stat2': 20})
    tmp_file = tmp_path / "test_report.xlsx"
    report.report(tmp_file)
    # open_file(tmp_file)
