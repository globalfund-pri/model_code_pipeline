import os
from typing import Dict

import pandas as pd
import pathlib

path_to_data_for_tests = (
    pathlib.Path(os.path.dirname(__file__)) / "code_and_data_for_tests"
)

def run_ic7_report(tmpdir: pathlib.Path) -> Dict:
    """Returns the results generated by the running the Report class. (Also generates that Excel file in a temporary
    location.)"""

    from scripts.ic7.analyses.main_results_for_investment_case import get_report

    r = get_report(
        load_data_from_raw_files=True,
        do_checks=False,
        run_analysis=True,
    )

    # Generate report (checking that it can be written to an Excel file)
    filename = tmpdir / 'test_report.xlsx'
    rtn_from_return = r.report(filename)

    # Return the results of the report
    return rtn_from_return


def test_ic7report(tmpdir):
    """
    This test runs the report for IC7 (including loading the model results from scratch and running the optimisation
     analysis) and checks that the results are the same as that obtained previously and which have been agreed to be
     the desired output from this code pipeline. In so doing, it also causes all the checks to be run, and the report
     to be written to the Excel file - but these ancillary outputs are not scrutinized in this test.
    """

    def make_sorted_series(df: pd.DataFrame) -> pd.Series:
        return df.set_index(['Function', 'Key']).sort_index()['Value']

    run_results = run_ic7_report(tmpdir)

    target_results = pd.read_csv(path_to_data_for_tests / 'IC7_Report_main_2024_07_25.csv')

    # Check for close agreement of the "main" results
    pd.testing.assert_series_equal(
        make_sorted_series(run_results["stats"]),
        make_sorted_series(target_results),
        rtol=0.0001,   # Relative tolerance for comparison
    )
