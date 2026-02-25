from pathlib import Path
from pprint import pprint
from typing import Optional, Dict

import pandas as pd

from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.workbook import Workbook

from tgftools.utils import current_date_and_time_as_string, get_commit_revision_number


class Report:
    """Base class for generating reports.

    This class provides core functionality to generate reports from model outputs. It can be
    inherited to accept sets of PortfolioProjections for different diseases. Each member
    function should either return a Dict of the form {<label>: <stat>} or a pd.DataFrame.
    These results are assembled into an output Excel file where dict contents are written
    to the 'Stats' worksheet and DataFrames are written to their own sheets.

    Attributes:
        parameters: Configuration parameters for the report.
    """

    def __init__(self, *args, parameters, **kwargs):
        """Initialize the Report class.

        Args:
            *args: Variable length argument list.
            parameters: Configuration parameters for the report.
            **kwargs: Arbitrary keyword arguments.
        """
        self.parameters = parameters

    def _get_all_funcs_to_generate_stats(self) -> list[str]:
        """Get all functions in the class that generate statistics.

        Returns a list of function names that will generate statistics. This includes any
        callable method with a name that does not start with "_" and is not called "report".

        Returns:
            A sorted list of function names that generate statistics.
        """
        return sorted(
            [
                name
                for name in dir(self)
                if (
                    not name.startswith("_")
                    and (not name.startswith("report"))
                    and callable(self.__getattribute__(name))
            )
            ]
        )

    def report(self, filename: Optional[Path] = None) -> Dict:
        """Run all member functions and generate a report.

        Executes all statistics-generating functions in the class, collects their results,
        and optionally saves them to an Excel file. Results are returned as a dictionary
        regardless of whether a file is written.

        Args:
            filename: Optional path where the Excel report should be saved. If None, no file
                is written.

        Returns:
            A dictionary containing the report results with the following structure:
                - 'stats': A DataFrame with columns ['Function', 'Key', 'Value'] containing
                  all scalar statistics from individual functions.
                - Additional keys: DataFrames returned by functions, using function names
                  as keys.

        Raises:
            ValueError: If a function returns a value that is neither a dict nor a DataFrame.
        """

        # Storage for all the results
        all_results_for_stats_pages = dict()
        all_results_for_individual_worksheets = dict()

        all_funcs = self._get_all_funcs_to_generate_stats()
        for ch_name in all_funcs:
            # pprint(f"** {ch_name} **")
            output = self.__getattribute__(ch_name)()
            # pprint(output)

            if isinstance(output, dict):
                all_results_for_stats_pages[ch_name] = output
            elif isinstance(output, pd.DataFrame):
                all_results_for_individual_worksheets[ch_name] = output
            else:
                raise ValueError(f"Return from {ch_name} function is not of recognised type ({type(ch_name)}).")

        # Compile the results for the 'stats' summary
        results_for_main = list()
        for func_name, func_results in all_results_for_stats_pages.items():
            for stat_name, stat_result in func_results.items():
                results_for_main.append([func_name, stat_name, stat_result])

        if filename is not None:
            # Write to Excel
            wb = Workbook()

            # Write to 'git' sheet with metadata
            work_sheet_info = wb.active
            work_sheet_info.title = 'git'
            work_sheet_info.append(['date-time stamp', current_date_and_time_as_string()])
            work_sheet_info.append(['commit', get_commit_revision_number()])

            # Write to 'stats' worksheet
            work_sheet_stats = wb.create_sheet()
            work_sheet_stats.title = 'stats'
            for line in results_for_main:
                work_sheet_stats.append(line)

            # Write parameters.toml into 'params' sheet
            work_sheet_params = wb.create_sheet()
            work_sheet_params.title = 'params'
            for i, line in enumerate(self.parameters.raw_store.splitlines()):
                work_sheet_params.append([f'Line #{i + 1}', line])

            # Write results to individual worksheets
            for func_name, func_results in all_results_for_individual_worksheets.items():
                work_sheet = wb.create_sheet()
                # Truncate to first ten characters due to Excel requirements
                work_sheet.title = func_name[0:10]
                for r in dataframe_to_rows(func_results.reset_index(), index=False, header=True):
                    work_sheet.append(r)

            # Do any post-processing that may be required
            self._post_processing_on_workbook(wb)

            # Save workbook to file
            wb.save(filename)

        # Return results in the same format as the Excel file:
        # - 'stats' key: DataFrame containing all scalar stats from individual functions
        # - Other keys: DataFrames from functions that returned DataFrames
        return {
            'stats': (
                pd.DataFrame(results_for_main)
                .rename(columns={0: 'Function', 1: 'Key', 2: 'Value'})
            ),
            **all_results_for_individual_worksheets,
        }

    def _post_processing_on_workbook(self, workbook: Workbook):
        """Perform post-processing on the workbook.

        This method can be overridden in subclasses to perform additional processing on the
        workbook, such as creating graphs on certain worksheets or applying formatting.

        Args:
            workbook: The openpyxl Workbook object to post-process.
        """
        pass
