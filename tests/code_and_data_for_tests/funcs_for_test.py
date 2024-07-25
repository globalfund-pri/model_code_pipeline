from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from tgftools.checks import CheckResult, DatabaseChecks, critical
from tgftools.database import Database
from tgftools.filehandler import (
    CalibrationData,
    Gp,
    ModelResults,
    NonTgfFunding,
    PartnerData,
    PFInputData,
    TgfFunding, Parameters,
)
from tgftools.report import Report
from tgftools.utils import get_root_path

"""
This file contains the classes that are defined specifically for dealing with the Test Data. Analogous versions
of these classes are needed for each disease in any 'real' analysis.
"""

class DiseaseXMixin:
    """Base class used as a `mix-in` that allows any inheriting class to have a property `disease_name` that returns
    the disease name."""
    @property
    def disease_name(self):
        return 'diseaseX'


class ModelResultsTestData(DiseaseXMixin, ModelResults):
    """This is the FileHandler for reading in the Test model results.
    A class similar to this is needed for reading in the results from each of the modelling teams.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def disease_name(self):
        """Return the disease name, corresponding to the names used in the Parameters class and parameters.toml file."""
        return 'diseaseX'

    def _build_df(self, path: Path) -> pd.DataFrame:
        """Read in the data and return a pd.DataFrame with multi-index (scenario_code, funding_fraction, country, year,
        indicator) and columns (low, central, high)."""
        # This is the simplest possible type of "loading" as the test data are already in the perfect format.
        # The corresponding version of this function for the other diseases will be more complex.
        return pd.read_csv(path).set_index(
            ["scenario_descriptor", "funding_fraction", "country", "year", "indicator"]
        )


class PartnerDataTest(DiseaseXMixin, PartnerData):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        # Load results from file, which is going to be the same for all the different scenario_descriptors
        pf = pd.read_csv(path)
        return (
            pd.concat({"default": pf, "alternative": pf})
            .reset_index()
            .rename(columns={"level_0": "scenario_descriptor"})
            .drop(columns="level_1")
            .set_index(["scenario_descriptor", "country", "year", "indicator"])
        )


class PFInputDataTest(DiseaseXMixin, PFInputData):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _build_df(self, path: Path) -> pd.DataFrame:
        return pd.read_csv(path).set_index(
            ["scenario_descriptor", "country", "year", "indicator"]
        )


class GpTestData(DiseaseXMixin, Gp):
    """The type of FileHandler that is used for holding the Global Plan data for a particular disease for the whole
    portfolio."""

    def _build_df(
        self,
        fixed_gp,
        model_results,
        partner_data,
        parameters,
    ) -> pd.DataFrame:
        """Reads in the data and return a pd.DataFrame with multi-index (year, indicator) and columns (central)."""
        # In usual GP's there would be a manipulation of a fixed decline and the partner data and model results.
        # But here for simplicity, we load up a file which already has the GP trajectory created.
        df = pd.read_csv(fixed_gp)
        # Return in expected format
        return pd.DataFrame(df.groupby(by=["year", "indicator"])["central"].sum())


class DatabaseChecksTest(DiseaseXMixin, DatabaseChecks):
    """This is the DatabaseChecks for the Test data. It used the new formulation of returning 'CheckResults', and uses
    a mixture of returning string, lists of string, list of figures and a dataframe."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.EXPECTED_COUNTRIES = sorted(
            {
                "A",
                "B",
            }
        )

    @critical
    def A_no_negatives_and_return(self, db: Database):
        """Check that there are no negative values in the model results.
        If fails, the `CheckResult.message` is a list of strings."""
        list_of_idx_where_any_negative = []
        for idx, row in db.model_results.df.iterrows():
            if (row < 0).any():
                list_of_idx_where_any_negative.append(idx)
        if not (0 == len(list_of_idx_where_any_negative)):
            return CheckResult(passes=False, message=list_of_idx_where_any_negative)

    def A_all_expected_countries_in_model_results(self, db: Database):
        """Check that each country required is recorded exactly once.
        Returns a string.
        """
        if not (self.EXPECTED_COUNTRIES == db.model_results.countries):
            return CheckResult(
                passes=False,
                message="Some missing/extra countries in the Model Results.",
            )


    def A_all_scenarios_have_same_beginning(self, db: Database):
        """Check that each model scenario has the same value for all indicators up to 2020.
        If fails, the `CheckResult.message` is a list of strings.
        """

        def columns_are_the_same(_df: pd.DataFrame):
            """Returns True if every column is found to be identical in the dataframe, False otherwise."""
            return all([(_df[_df.columns[0]] == _df[c]).all() for c in _df.columns])

        # Find scenario descriptors to compare, skipping any scenarios noted as being a counterfactual
        scenario_descriptors_to_compare = self.parameters.get_scenarios().index.to_list()

        list_of_problem_lines = []  # Capture messages where a problem is detected
        for indicator in db.model_results.indicators:
            for country in db.model_results.countries:
                model_results_up_to_2020 = dict()
                for scenario_descriptor in scenario_descriptors_to_compare:
                    for funding_fraction in db.model_results.funding_fractions:
                        # Extract model_central run up to 2020
                        model_results_up_to_2020[
                            f"{country=}|{scenario_descriptor=}|{funding_fraction=}|{indicator=}"
                        ] = db.get_country(
                            country=country,
                            scenario_descriptor=scenario_descriptor,
                            funding_fraction=funding_fraction,
                            indicator=indicator,
                        ).loc[
                            0:2020, "model_central"
                        ]

                y = pd.DataFrame(model_results_up_to_2020)
                if not columns_are_the_same(y):
                    list_of_problem_lines.append(
                        f"Some scenarios are different: {country=}, {indicator=}"
                    )

        # There should be no messages. But, if they are, return CheckResult indicating the error.
        if len(list_of_problem_lines):
            return CheckResult(passes=False, message=list_of_problem_lines)

    def A_all_scenarios_match_partner_data_within_a_tolerance(self, db: Database):
        """Check that the model results (central) match the corresponding partner data for all the partner data
        indicators, within a relative tolerance of 5%.
        If fails, the `CheckResult.message` is a list of strings."""
        RELATIVE_TOLERANCE = 0.05

        list_of_problem_lines = []  # Capture messages where a problem is detected
        for (
            indicator
        ) in db.partner_data.indicators:  # Limit to partner data's indicators
            for country in db.model_results.countries:
                for scenario_descriptor in db.model_results.scenario_descriptors:
                    for funding_fraction in db.model_results.funding_fractions:
                        country_df = db.get_country(
                            country=country,
                            scenario_descriptor=scenario_descriptor,
                            indicator=indicator,
                            funding_fraction=funding_fraction,
                        ).dropna(
                            how="any", axis=0
                        )  # drop rows with na's (years with no partner data)

                        within_tolerance = np.allclose(
                            country_df["model_central"],
                            country_df["partner_central"],
                            rtol=RELATIVE_TOLERANCE,
                        )

                        if not within_tolerance:
                            list_of_problem_lines.append(
                                f"Some calibration mismatch for: {country=}, {scenario_descriptor=}, "
                                f"{funding_fraction=}, {indicator=}."
                            )
        # There should be no messages. But, if they are, return CheckResult indicating the error.
        if len(list_of_problem_lines):
            return CheckResult(passes=False, message=list_of_problem_lines)

    @staticmethod
    def X_return_a_table(_):
        """Always passes, and the `CheckResult.message` is a pd.DataFrame"""
        return CheckResult(
            passes=True,
            message=pd.DataFrame(
                index=range(2), columns=["country", "indicator"], data=[[0, 1], [2, 3]]
            ),
        )

    @staticmethod
    def X_return_a_list_of_tables(_):
        """Always passes, and the `CheckResult.message` is a list of pd.DataFrames."""
        table = pd.DataFrame(
            index=range(2), columns=["country", "indicator"], data=[[0, 1], [2, 3]]
        )

        return CheckResult(
            passes=True,
            message=[
                table,
                table,
                table,
            ],
        )

    @staticmethod
    def Z_return_a_figure(_):
        """Check passes and returns a random figure.
        The `CheckResult.message` is a figure.
        """

        def make_a_graph(title: str):
            """Returns fig of made-up data"""
            fig, ax = plt.subplots()
            pd.DataFrame(np.random.rand(10, 5)).plot(ax=ax)
            ax.set_title(title)
            fig.tight_layout()
            return fig

        return CheckResult(passes=True, message=make_a_graph("My graph"))

    @staticmethod
    def Z_return_a_list_of_figures(db: Database):
        """Check passes and returns some random figures.
        The `CheckResult.message` is a list of figure."""

        def _make_fig(country, indicator):
            fig, ax = plt.subplots()
            db.get_country(
                country=country,
                scenario_descriptor="default",
                funding_fraction=1.0,
                indicator=indicator,
            ).plot(ax=ax)
            ax.set_title(f"{country=} | {indicator=}")
            return fig

        figs = []
        for country in db.model_results.countries:
            for indicator in db.model_results.indicators:
                figs.append(_make_fig(country, indicator))

        return CheckResult(passes=True, message=figs)


if __name__ == "__main__":
    # This is an entry-point to this file. It demonstrates how these classes can be used in a real analysis.

    # Load the files
    path_to_data_for_tests = get_root_path() / "tests" / "code_and_data_for_tests"

    parameters = Parameters(path_to_data_for_tests / "parameters.toml")

    database = Database(
        model_results=ModelResultsTestData(
            path_to_data_for_tests / "model_results.csv",
            parameters=parameters,
        ),
        gp=GpTestData(
            fixed_gp=path_to_data_for_tests / "gp.csv",
            model_results=None,
            partner_data=None,
            parameters=parameters,
        ),
        partner_data=PartnerDataTest(path_to_data_for_tests / "partner_data.csv"),
        pf_input_data=PFInputDataTest(path_to_data_for_tests / "pf.csv"),
    )

    # Run the checks
    DatabaseChecksTest(db=database, parameters=parameters).run()


class TestReport(Report):

    def __init__(self, diseaseX, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.diseaseX = diseaseX

    def get_stats_and_return_as_dict(self) -> Dict[str, float]:
        return {'stat1': self.diseaseX['stat1'], 'stat2': self.diseaseX['stat2']}

    def get_stats_and_return_as_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame({
            'column1': pd.Series({'stat1': self.diseaseX['stat1'], 'stat2': self.diseaseX['stat2']}),
        })
