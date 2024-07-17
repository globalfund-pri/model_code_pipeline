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

from tgftools.database import Database

path_to_data_for_tests = (
    pathlib.Path(os.path.dirname(__file__)) / "code_and_data_for_tests"
)


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


def test_get_country(database):
    df = database.get_country(
        country="A",
        indicator="deaths",
        scenario_descriptor="alternative",
        funding_fraction=0.8,
    )
    assert isinstance(df, pd.DataFrame)
