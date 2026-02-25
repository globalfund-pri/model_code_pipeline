from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Callable, Dict, List, Optional

import matplotlib.figure
import pandas as pd
import reportlab
from matplotlib import pyplot as plt
from openpyxl.descriptors import Bool
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Image, SimpleDocTemplate, Spacer
from reportlab.platypus.para import Paragraph

from tgftools.database import Database
from tgftools.filehandler import Parameters
from tgftools.utils import (
    current_date_and_time_as_string,
    deEmojify,
    get_root_path,
    wipe,
    get_commit_revision_number)
from tgftools.write_to_pdf import df2table, fig2image

"""This module contains everything needed for the DatabaseChecks class.

This module provides the DatabaseChecks base class and supporting utilities for
performing data validation checks on Database objects. It includes decorators,
result classes, and reporting functionality.
"""


class DataCheckError(Exception):
    """Exception raised when data checks fail."""
    pass


@dataclass
class CheckResult:
    """Result of a single data validation check.

    This dataclass encapsulates the outcome of a single check performed on a
    database, including whether it passed and an optional message.

    Attributes:
        passes: Whether the check passed validation.
        message: Optional message providing details about the check result. Can be
            a string, matplotlib figure, or list of strings/figures.
    """

    passes: bool = None
    message: [
        str,
        matplotlib.figure.Figure,
        list[str],
        list[matplotlib.figure.Figure],
    ] = None


@dataclass
class CheckReport:
    """Report generated from running a single data validation check.

    This dataclass captures comprehensive information about a check execution,
    including metadata, results, and any associated messages or visualizations.

    Attributes:
        name: Name of the check function.
        description: Description of what the check validates.
        is_critical: Whether this check is marked as critical.
        passes: Whether the check passed validation.
        message: Optional message providing details about the check result. Can be
            a string, matplotlib figure, or list of strings/figures.
    """

    name: str = None
    description: str = None
    is_critical: bool = False
    passes: bool = False
    message: [
        str,
        matplotlib.figure.Figure,
        list[str],
        list[matplotlib.figure.Figure],
    ] = None


def critical(func):
    """Decorator to mark a check function as critical.

    Critical checks are treated with higher priority in reporting and may
    trigger different error handling behavior when they fail.

    Args:
        func: The check function to be marked as critical.

    Returns:
        The wrapped function with a 'critical' attribute set to True.
    """

    @wraps(func)
    def wrapped(*args, **kwargs):
        return func(*args, **kwargs)

    wrapped.critical = True
    return wrapped


def is_critical(func):
    """Check if a function has been decorated with the @critical decorator.

    Args:
        func: The function to check for the critical attribute.

    Returns:
        True if the function has been marked as critical, False otherwise.

    Note:
        Implementation based on https://stackoverflow.com/a/68583930
    """
    return getattr(func, "critical", False)


class DatabaseChecks:
    """Base class for performing validation checks on Database objects.

    This class provides the infrastructure for defining and running validation
    checks on Database objects. Subclasses should define check methods that
    validate specific aspects of the data.

    Each check method in a subclass should:
    - Have an informative name describing what is being tested
    - Include a docstring explaining exactly what is being validated
    - Use `assert` statements to indicate conditions that must be True
    - Return a CheckResult instance with pass/fail status and optional message
    - Use the @critical decorator for checks that are considered critical

    The class distinguishes between critical and non-critical check failures,
    providing different reporting and error handling for each type.

    Attributes:
        db: The Database object to perform checks on.
        parameters: Optional Parameters object for configuration.
        ccr: ConsolidatedChecksReport for aggregating check results.

    Args:
        db: The Database object to perform checks on.
        parameters: Optional Parameters object for configuration.
    """

    def __init__(self, db: Database, parameters: Optional[Parameters] = None):
        self.db = db
        self.parameters = parameters
        self.ccr = ConsolidatedChecksReport(
            title=type(self).__name__,
            doc=str(self.__doc__).replace("\n", ""),
            filenames={
                "Model Results": str(self.db.model_results.path),
                "Partner Data": str(self.db.partner_data.path) if self.db.partner_data is not None else "None",
                "PF Input Data": str(self.db.pf_input_data.path) if self.db.pf_input_data is not None else "None",
            },
        )

    def _run_check(self, the_func: Callable) -> CheckReport:
        """Execute a single check function and return a CheckReport.

        This method handles check execution, capturing both successful results
        and failures. It interprets different return values and exception types
        to determine the check outcome.

        Behavior:
        - If check returns None, it is assumed to have passed.
        - If check returns a CheckResult, that result is used.
        - If an AssertionError is raised, the check is marked as failed with
          the error message captured.

        Args:
            the_func: The check function to execute, which should accept a
                Database object and return a CheckResult or None.

        Returns:
            A CheckReport containing the check metadata and execution results.

        Raises:
            ValueError: If the check returns an unexpected type.
        """
        # Capture the static information about the check.
        header = dict(
            name=the_func.__name__,
            description=the_func.__doc__,
            is_critical=is_critical(the_func),
        )

        try:
            ch_res: CheckResult = the_func(self.db)
            if ch_res is None:
                return CheckReport(**header, passes=True, message="")
            elif isinstance(ch_res, CheckResult):
                return CheckReport(
                    **header, passes=ch_res.passes, message=ch_res.message
                )
            else:
                raise ValueError(f"Check {the_func} returned unexpected item")

        except AssertionError as assertion_error:
            message_in_assertion_error = assertion_error.args[0].split("\n")[0]
            return CheckReport(
                **header, passes=False, message=message_in_assertion_error
            )

    def run(
        self,
        suppress_error: Optional[bool] = False,
        verbose: bool = False,
        filename: Optional[Path] = None,
    ) -> bool:
        """Execute all defined checks and report results.

        This method discovers and runs all check methods defined in the class,
        generates a consolidated report, and optionally saves results to a PDF.
        A summary is printed to the console.

        Args:
            suppress_error: If True, prevents raising DataCheckError when checks
                fail. Defaults to False.
            verbose: If True, includes detailed information about all checks in
                the console output. Defaults to False.
            filename: Optional path to save the check results as a PDF report.

        Returns:
            True if all checks passed, False otherwise.

        Raises:
            DataCheckError: If any checks fail and suppress_error is False.
        """

        # Run all the checks
        wipe()
        print(f"✨ Initiating checks {self.__class__} ✨")
        check_names = self._get_check_names()
        for ch_name in check_names:
            ch_func: Callable = self.__getattribute__(ch_name)
            print(f"Running: {ch_name} .....", end="")
            self.ccr.add_check_report(self._run_check(ch_func))
            print("Done!")

        # Report (print to console and, optionally, create pdf)
        self.ccr.report(filename=filename, verbose=verbose)

        # Determine if error should be thrown
        if self.ccr.any_fails and (not suppress_error):
            raise DataCheckError("Some checks have failed.")

        # Determine the outcome bool (True if there have been no fails)
        return not self.ccr.any_fails

    def _get_check_names(self) -> list:
        """Discover and return the names of all check methods in the class.

        A check method is identified as any callable attribute that:
        - Does not start with '_' (private methods)
        - Does not start with 'XX' (disabled methods)
        - Does not start with 'run_' (runner methods)
        - Is not named 'run' (the main runner method)

        Returns:
            A sorted list of check method names found in the class.
        """
        return sorted(
            set(
                [
                    name
                    for name in dir(self)
                    if (
                        not name.startswith("_")
                        and (not name.startswith("XX"))
                        and (not name.startswith("run_"))
                        and callable(self.__getattribute__(name))
                    )
                ]
            )
            - {"run"}
        )

    # Example check method template:
    # def my_check(self, db: Database) -> CheckResult:
    #     """Example check demonstrating proper check method structure.
    #
    #     This docstring describes what the check validates and is captured in
    #     the output reports. Each check should interrogate the database and
    #     return a CheckResult instance.
    #
    #     Args:
    #         db: The Database object to validate.
    #
    #     Returns:
    #         CheckResult indicating whether the check passed, with an optional
    #         message (string, matplotlib figure, pandas dataframe, or list).
    #     """
    #     return CheckResult(passes=True, message='')


class ConsolidatedChecksReport:
    """Aggregates and formats individual check reports into a consolidated report.

    This class collects CheckReport instances from multiple checks and generates
    a comprehensive report that can be printed to console and saved as a PDF.
    The report includes metadata, summary statistics, and detailed results for
    all checks.

    Attributes:
        flowables: List of ReportLab flowable objects for PDF generation.
        styles: ReportLab stylesheet for PDF formatting.
        spacer: Standard vertical spacing element for PDF layout.
        small_spacer: Small vertical spacing element for PDF layout.
        horizontal_line: Horizontal rule element for PDF layout.

    Args:
        title: Title of the report (typically the check class name).
        doc: Documentation string describing the purpose of the checks.
        filenames: Dictionary mapping data source names to their file paths.
    """

    def __init__(self, title: str, doc: str, filenames: Dict):
        self._title = title
        self._doc = doc
        self._filenames = filenames
        self._check_reports = list()

        # Create empty list for the "flowables" for the pdf generation
        self.flowables = []

        # Load components for pdf generation
        self.styles = getSampleStyleSheet()
        self.spacer = Spacer(1, 0.25 * inch)
        self.small_spacer = Spacer(1, 0.1 * inch)
        self.horizontal_line = HRFlowable()

    def add_check_report(self, ch_rep: CheckReport = None):
        """Add a CheckReport to the consolidated report.

        This method validates the message format and stores the check report
        for later aggregation and reporting.

        Args:
            ch_rep: The CheckReport to add to the consolidated report.

        Raises:
            AssertionError: If the message type is not supported (must be
                pd.DataFrame, plt.Figure, str, tuple, or None).
        """

        # if the message is an empty list, replace it with it None
        if isinstance(ch_rep.message, list) and len(ch_rep.message) == 0:
            ch_rep.message = None

        # Check that the message is of the right type (or none)
        if ch_rep.message is not None:
            item_types = (pd.DataFrame, plt.Figure, str, tuple)
            single_element = (
                ch_rep.message[0]
                if isinstance(ch_rep.message, list)
                else ch_rep.message
            )
            assert isinstance(single_element, item_types), (
                f"Message is of the wrong type {ch_rep.message=}, "
                f"{single_element=}, type: {type(single_element)}"
            )

        # Add to internal storage list of CheckReports
        self._check_reports.append(ch_rep)

    @property
    def passing_checks(self) -> List:
        """Get all check reports that passed.

        Returns:
            List of CheckReport instances where passes is True.
        """
        return [rep for rep in self._check_reports if rep.passes]

    @property
    def non_critical_failing_checks(self) -> List:
        """Get all non-critical check reports that failed.

        Returns:
            List of CheckReport instances that failed and are not marked as critical.
        """
        return [
            rep for rep in self._check_reports if not rep.passes and not rep.is_critical
        ]

    @property
    def critical_failing_checks(self) -> List:
        """Get all critical check reports that failed.

        Returns:
            List of CheckReport instances that failed and are marked as critical.
        """
        return [
            rep for rep in self._check_reports if not rep.passes and rep.is_critical
        ]

    @property
    def any_fails(self) -> Bool:
        """Check if any checks (critical or non-critical) have failed.

        Returns:
            True if any checks failed, False otherwise.
        """
        return any(self.critical_failing_checks) or any(
            self.non_critical_failing_checks
        )

    def _print(self, item, style=None, echo_to_console=True) -> None:
        """Print content to console and add to PDF flowables list.

        This internal method handles different types of content (strings,
        figures, dataframes) and formats them appropriately for both console
        output and PDF generation.

        Special string commands:
        - "\\n": Insert blank line/spacer
        - "---": Insert horizontal line
        - "ICON=filename": Insert icon image from resources

        Args:
            item: The content to print. Can be a string, matplotlib figure,
                pandas dataframe, or list of these types.
            style: ReportLab style to apply to text. Defaults to "Normal".
            echo_to_console: If True, also print to console. Defaults to True.
        """

        if style is None:
            style = self.styles["Normal"]

        def handle_item(this_item):
            if isinstance(this_item, str):
                if this_item == "\n":
                    # Handle blank line command
                    if echo_to_console:
                        print("\n")
                    self.flowables.append(self.spacer)

                elif this_item == "---":
                    # Insert horizontal line
                    if echo_to_console:
                        print("--------------------------------------------------")
                    self.flowables.append(self.horizontal_line)

                elif this_item.startswith("ICON="):
                    # Insert icon indicated
                    icon_file = Path(
                        get_root_path()
                        / "resources"
                        / "icons"
                        / this_item.split("ICON=")[1]
                    )
                    self.flowables.append(Image(icon_file, 50, 50))

                else:
                    # Handle simple string
                    if this_item != "":
                        if echo_to_console:
                            print(this_item)
                        self.flowables.append(Paragraph(deEmojify(this_item), style))

            elif isinstance(this_item, plt.Figure):
                if echo_to_console:
                    this_item.show()
                self.flowables.append(fig2image(this_item))

            elif isinstance(this_item, pd.DataFrame):
                if echo_to_console:
                    print(this_item.head())
                self.flowables.append(df2table(this_item))

            else:
                # item type not recognised: ignore
                pass

        if item is None:
            # If the item is None, then do nothing
            return

        elif isinstance(item, list):
            # If the item is actually a list of items, handle each item in turn
            for i in item:
                handle_item(i)
                self.flowables.append(self.small_spacer)
        else:
            # If the item is a single item, just handle it.
            handle_item(item)

    def _generate_report(self, verbose):
        """Generate the formatted report content for console and PDF output.

        This method compiles all check results into a structured report with
        sections for critical failures, non-critical failures, and passing checks.
        The report includes metadata such as file paths, timestamps, and git
        commit information.

        Args:
            verbose: If True, includes detailed messages for all checks in
                console output. PDF always includes full details.
        """
        self.flowables = []
        self.flowables.append(
            Image(get_root_path() / "resources/icons/logo.jpg", 100, 50)
        )
        self._print(f"\n")
        self._print(self._title, style=self.styles["Heading1"])
        self._print(self._doc, style=self.styles["Normal"])
        self._print(f"\n")
        self._print(current_date_and_time_as_string(), style=self.styles["Heading3"])


        self._print(f"\n")
        self._print("Files Used:", style=self.styles["Heading3"])
        for k, v in self._filenames.items():
            self._print(f"* {k}: {v}", style=self.styles["Normal"])
        self._print(f"\n")
        self._print(f"Git Commit: {get_commit_revision_number()}")
        self._print("---")

        # Determine summary outcome of the set of checks
        self._print(f"\n")
        if any(self.critical_failing_checks):
            self._print(
                "❌Some checks have failed, including some that are CRITICAL.",
                style=self.styles["Heading2"],
            )
            self._print("ICON=cross.jpg")
        elif any(self.non_critical_failing_checks):
            self._print(
                "🤷Some checks have failed, but none are CRITICAL.",
                style=self.styles["Heading2"],
            )
            self._print("ICON=shrug.jpg")
        else:
            self._print("✅All checks passed.", style=self.styles["Heading2"])
            self._print("ICON=tick.jpg")
        self._print(f"\n")
        self._print("---")

        # Print details of each check to the console
        if any(self.critical_failing_checks):
            self._print(f"\n")
            self._print("🚨CRITICAL FAILING CHECKS", style=self.styles["Heading2"])
            for f in self.critical_failing_checks:
                self._print(f"    👎FAILED: {f.name}", style=self.styles["Heading3"])
                self._print(f"({f.description})")
                self._print(
                    f.message, style=self.styles["Normal"], echo_to_console=verbose
                )
                self._print(f"\n", echo_to_console=verbose)
            self._print("---")

        if any(self.non_critical_failing_checks):
            self._print(f"\n")
            self._print(f"\n")
            self._print("🤔 NON-CRITICAL FAILING CHECKS", style=self.styles["Heading2"])
            for f in self.non_critical_failing_checks:
                self._print(f"    👎FAILED: {f.name}", style=self.styles["Heading3"])
                self._print(f"({f.description})")
                self._print(
                    f.message, style=self.styles["Normal"], echo_to_console=verbose
                )
                self._print("\n", echo_to_console=verbose)
            self._print("---")

        if any(self.passing_checks):
            self._print(f"\n")
            self._print(f"\n")
            self._print("❤️ PASSING CHECKS", style=self.styles["Heading2"])
            for f in self.passing_checks:
                self._print(f"    👍PASSED: {f.name}", style=self.styles["Heading3"])
                self._print(f"({f.description})")
                self._print(
                    f.message, style=self.styles["Normal"], echo_to_console=verbose
                )
                self._print("\n", echo_to_console=verbose)
            self._print("---")

    def report(self, filename: Optional[Path], verbose: bool):
        """Generate and output the consolidated checks report.

        This method generates the report content and outputs it to the console.
        If a filename is provided, it also saves the report as a PDF.

        Args:
            filename: Optional path where the PDF report should be saved. If None,
                no PDF is generated.
            verbose: If True, includes detailed information about all checks in
                the console output. If False, only summary information is shown.
        """
        self._generate_report(verbose=verbose)

        if filename is not None:
            print(f"Writing to pdf at: {filename}: ....", end="")
            doc = SimpleDocTemplate(str(filename), pageSize=reportlab.lib.pagesizes.A4)
            doc.build(self.flowables)
            print("Done!")
