from typing import Dict, Callable

import pandas as pd
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from pathlib import Path


class DumpAnalysisToExcel:
    """Helper class for exporting Analysis results to Excel.

    This class manages the export of all analysis results to an Excel workbook.
    Each method that returns a DataFrame is automatically saved into a worksheet
    named after the method. The class also runs approach_a and computes the
    counterfactual during initialization.

    Attributes:
        analysis: The Analysis instance to export data from.
        filename: Path where the Excel file will be saved.
        approach_a: Results from portfolio_projection_approach_a().
        wb: The openpyxl Workbook object being created.
    """

    def __init__(self, analysis: 'Analysis', filename: Path):
        """Initialize the DumpAnalysisToExcel instance.

        Args:
            analysis: The Analysis instance to export data from.
            filename: Path where the Excel file will be saved.
        """
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
        """Get all public methods that return DataFrames.

        Returns:
            Dictionary mapping function names to function objects. Only methods
            that don't begin with '_' are included.
        """
        return {
            name: self.__getattribute__(name)
            for name in dir(self)
            if (not name.startswith("_") and callable(self.__getattribute__(name)))
        }

    def _write_df_to_sheet(self, sheetname: str, df: pd.DataFrame) -> None:
        """Write the content of a DataFrame to a worksheet.

        Args:
            sheetname: Name of the worksheet to create.
            df: DataFrame to write to the worksheet.

        Raises:
            TypeError: If df is not a pandas DataFrame.
        """
        if not isinstance(df, pd.DataFrame):
            raise TypeError(f"Return for {sheetname} is not a pd.DataFrame.")

        self.wb.create_sheet(sheetname)
        ws = self.wb[sheetname]
        for r in dataframe_to_rows(df, index=True, header=True):
            ws.append(r)

    def non_tgf_funding(self) -> pd.DataFrame:
        """Get non-TGF funding data.

        Returns:
            DataFrame containing non-TGF funding information.
        """
        return self.analysis.non_tgf_funding.df

    def tgf_funding(self) -> pd.DataFrame:
        """Get TGF funding data.

        Returns:
            DataFrame containing TGF funding information.
        """
        return self.analysis.tgf_funding.df

    def approach_a_portfolio_cases(self) -> pd.DataFrame:
        """Get approach A portfolio cases.

        Returns:
            DataFrame containing portfolio-level case projections from approach A.
        """
        return self.approach_a.portfolio_results['cases']

    def approach_a_portfolio_deaths(self) -> pd.DataFrame:
        """Get approach A portfolio deaths.

        Returns:
            DataFrame containing portfolio-level death projections from approach A.
        """
        return self.approach_a.portfolio_results['deaths']

    def approach_a_portfolio_cost(self) -> pd.DataFrame:
        """Get approach A portfolio cost.

        Returns:
            DataFrame containing portfolio-level cost projections from approach A.
        """
        return self.approach_a.portfolio_results['cost']

    def approach_a_cases_by_country(self) -> pd.DataFrame:
        """Get unadjusted model results for cases by country.

        Returns:
            DataFrame containing case projections by country (not adjusted).
        """
        cr = self.approach_a.country_results
        return pd.concat(
            {
                country_name: results.model_projection['cases'] for country_name, results in cr.items()
            }
        ).reset_index().rename(columns={'level_0': 'country'}).set_index('country')

    def approach_a_deaths_by_country(self) -> pd.DataFrame:
        """Get unadjusted model results for deaths by country.

        Returns:
            DataFrame containing death projections by country (not adjusted).
        """
        cr = self.approach_a.country_results
        return pd.concat(
            {
                country_name: results.model_projection['deaths'] for country_name, results in cr.items()
            }
        ).reset_index().rename(columns={'level_0': 'country'}).set_index('country')

    # todo intermediary outputs during adjustments

    # todo output cost-impact curves

    # todo outputs for approach_b
