from typing import Dict, Callable

import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from pathlib import Path


class DumpAnalysisToExcel:
    """Helper class to manage dumping everything in the Analysis class into Excel.
    Each function return a pd.DataFrame, which is saved into an Excel worksheet named the same as the function.
    This function also has to run approach_a, appproach_b and compute the counterfactual <--- todo how to avoid repeatition??
    """

    def __init__(self, analysis: 'Analysis', filename: Path):
        self.analysis = analysis
        self.filename = filename

        # Do all the analyses
        self.approach_a = self.analysis.portfolio_projection_approach_a()

        # Make Workbook
        self.wb = Workbook()

        # Report key information into a sheet called `main`
        ws = self.wb.active
        ws.title = "main"
        ws.append(['disease_name', self.analysis.disease_name])
        ws.append(['scenario_descriptor', self.analysis.scenario_descriptor])

        # Run all the functions in this class and save their results to the workbook
        all_funcs = self._get_all_funcs()
        for func_name, func in all_funcs.items():
            self._write_df_to_sheet(
                sheetname=func_name,
                df=func(),
            )

        # Save Workbook
        self.wb.save(self.filename)

    def _get_all_funcs(self) -> Dict[str, Callable]:
        """Returns dict of the form {function_name: function}. Every function is returned except those beginning with
        `_`.
        """
        return {
            name: self.__getattribute__(name)
            for name in dir(self)
            if (not name.startswith("_") and callable(self.__getattribute__(name)))
        }

    def _write_df_to_sheet(self, sheetname: str, df: pd.DataFrame) -> None:
        """Write the content of `df` to a worksheet named `sheetname`."""
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Return for {sheetname} is not a pd.DataFrame.")

        self.wb.create_sheet(sheetname)
        ws = self.wb[sheetname]
        for r in dataframe_to_rows(df, index=True, header=True):
            ws.append(r)

    def non_tgf_funding(self) -> pd.DataFrame:
        return self.analysis.non_tgf_funding.df

    def tgf_funding(self) -> pd.DataFrame:
        return self.analysis.tgf_funding.df

    def non_tgf_funding(self) -> pd.DataFrame:
        return self.analysis.non_tgf_funding.df

    def approach_a_portfolio_cases(self) -> pd.DataFrame:
        return self.approach_a.portfolio_results['cases']

    def approach_a_portfolio_deaths(self) -> pd.DataFrame:
        return self.approach_a.portfolio_results['deaths']

    def approach_a_portfolio_cost(self) -> pd.DataFrame:
        return self.approach_a.portfolio_results['cost']

    def approach_a_cases_by_country(self) -> pd.DataFrame:
        """This is the not-adjusted model results for cases by country"""
        cr = self.approach_a.country_results
        return pd.concat(
            {
                country_name: results.model_projection['cases'] for country_name, results in cr.items()
            }
        ).reset_index().rename(columns={'level_0': 'country'}).set_index('country')

    def approach_a_deaths_by_country(self) -> pd.DataFrame:
        """This is the not-adjusted model results for cases by country"""
        cr = self.approach_a.country_results
        return pd.concat(
            {
                country_name: results.model_projection['deaths'] for country_name, results in cr.items()
            }
        ).reset_index().rename(columns={'level_0': 'country'}).set_index('country')

    # todo intermediary outputs during adjustments

    # todo output cost-impact curves

    # todo outputs for approach_b
