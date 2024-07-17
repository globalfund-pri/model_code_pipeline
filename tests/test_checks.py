import os
import pathlib

import pytest
from code_and_data_for_tests.funcs_for_test import (
    DatabaseChecksTest,
    GpTestData,
    ModelResultsTestData,
    PartnerDataTest,
    PFInputDataTest,
)

from tgftools.checks import CheckResult, DatabaseChecks
from tgftools.database import Database
from tgftools.filehandler import Parameters

path_to_data_for_tests = (
    pathlib.Path(os.path.dirname(__file__)) / "code_and_data_for_tests"
)


@pytest.fixture
def parameters():
    return Parameters(path_to_data_for_tests / "parameters.toml")

@pytest.fixture
def database(parameters):
    return Database(
        model_results=ModelResultsTestData(
            path_to_data_for_tests / "model_results.csv",
            parameters=parameters
        ),
        gp=GpTestData(
            fixed_gp=path_to_data_for_tests / "gp.csv",
            model_results=None,
            partner_data=None,
        ),
        partner_data=PartnerDataTest(path_to_data_for_tests / "partner_data.csv"),
        pf_input_data=PFInputDataTest(path_to_data_for_tests / "pf.csv"),
    )




def cause_failure_of_non_critical_check(database):
    # Modify the data in such a way as to cause the failure of a non-critical check.
    # (A modification in the model_results in one scenario in the first year will cause the check
    # `DatabaseChecksTest:all_scenarios_have_same_beginning_and_match_calibration` to fail, but that check is not
    # labelled as being critical.)
    database.model_results.df.loc[
        ("default", 0.8, "A", 2010, "cases"), "central"
    ] *= 0.5


def cause_failure_of_critical_check(database):
    # Modify the data in such a way as to cause the failure of a critical check.
    # (A negative value will cause the check `DatabaseChecksTest:no_negatives` to fail and that check is labelled
    # as being critical.)
    model_results_df = database.model_results.df
    model_results_df.loc[model_results_df.index[0], "central"] = -1.0


def test_data_checks_test_passes(database, parameters):
    """Checks on the test data should all pass when the data are not modified and the log should be written accordingly."""

    # Run the checks on a set of data that should pass all the checks -->  no errors & 'True' returned
    checks = DatabaseChecksTest(db=database, parameters=parameters)
    assert True is checks.run()

    # ... and internal storage should reflect all checks passing
    assert any(checks.ccr.passing_checks)
    assert not any(checks.ccr.critical_failing_checks)
    assert not any(checks.ccr.non_critical_failing_checks)


def test_data_checks_test_critical_fail(database, parameters):
    """Checks on the test data should reveal a critical failure when the test data are modified such that critical check
    fails."""

    cause_failure_of_critical_check(database)

    # Run check --> An error should be raised
    from tgftools.checks import DataCheckError

    checks = DatabaseChecksTest(db=database, parameters=parameters)
    with pytest.raises(DataCheckError):
        assert False is checks.run()

    # Run the check with option to suppress error --> No error should be raised
    # check critical check failure detected
    checks = DatabaseChecksTest(database, parameters=parameters)
    assert False is checks.run(suppress_error=True)
    assert any(checks.ccr.critical_failing_checks)


def test_data_checks_test_non_critical_fail(database, parameters):
    """Checks on the test data should reveal a non-critical failure when the test data are modified such that
    a non-critical check fails (and no critical checks fail)."""

    cause_failure_of_non_critical_check(database)

    # Run check --> An error should be raised
    from tgftools.checks import DataCheckError

    checks = DatabaseChecksTest(db=database, parameters=parameters)
    with pytest.raises(DataCheckError):
        assert False is checks.run()

    # Run the check with option to suppress error --> No error should be raised
    # check critical check failure detected
    checks = DatabaseChecksTest(database, parameters=parameters)
    assert False is checks.run(suppress_error=True)
    assert any(checks.ccr.non_critical_failing_checks)
    assert not any(checks.ccr.critical_failing_checks)


def test_generate_pdf_from_checks_all_passing(database, parameters, tmpdir):
    """Check that a pdf can be generated based on the checks, with all checks passing."""
    report_filename = tmpdir / "report.pdf"

    # With All tests passing
    assert not report_filename.exists()  # check that the file does not exist already
    checks = DatabaseChecksTest(db=database, parameters=parameters)
    checks.run(filename=report_filename)
    assert report_filename.exists()  # check file has been created

    # from tgftools.utils import open_file
    # open_file(report_filename)


def test_generate_pdf_from_checks_with_critical_failures(database, parameters, tmpdir):
    """Check that a pdf can be generated based on the checks, including failures."""
    report_filename = tmpdir / "report.pdf"

    # critical and non-critical failures
    cause_failure_of_critical_check(database)
    cause_failure_of_non_critical_check(database)

    # With All tests passing
    assert not report_filename.exists()  # check that the file does not exist already
    checks = DatabaseChecksTest(db=database, parameters=parameters)
    checks.run(suppress_error=True, filename=report_filename)
    assert report_filename.exists()  # check file has been created
    # open_file(report_filename)


def test_generate_pdf_from_checks_with_non_critical_failures(database, parameters, tmpdir):
    """Check that a pdf can be generated based on the checks, including failures."""
    report_filename = tmpdir / "report.pdf"

    # critical and non-critical failures
    cause_failure_of_non_critical_check(database)

    # With All tests passing
    assert not report_filename.exists()  # check that the file does not exist already
    checks = DatabaseChecksTest(db=database, parameters=parameters)
    checks.run(suppress_error=True, filename=report_filename)
    assert report_filename.exists()  # check file has been created
    # open_file(report_filename)


def test_outputs_from_check_can_be_assertion_nothing_or_check_result_object(database, parameters):
    """Check that the outcome of a check can be implicitly (return nothing), through an AssertionError, or through
    a return of CheckResult."""

    class MyChecks(DatabaseChecks):
        def passes_and_returns_nothing(self, _):
            """passes_and_returns_nothing"""
            pass

        @staticmethod
        def fails_and_raised_assertion_error_as_string(_):
            """fails_and_raised_assertion_error_as_string"""
            assert False, "My failing message"

        @staticmethod
        def fails_and_raised_check_result_with_no_message(_):
            return CheckResult(passes=False)

    checks = MyChecks(db=database, parameters=parameters)
    checks.run(suppress_error=True, verbose=False)

    assert {"passes_and_returns_nothing"} == set(
        [c.name for c in checks.ccr.passing_checks]
    )

    assert {
        "fails_and_raised_assertion_error_as_string",
        "fails_and_raised_check_result_with_no_message",
    } == set([c.name for c in checks.ccr.non_critical_failing_checks])

    assert set() == set([c.name for c in checks.ccr.critical_failing_checks])
