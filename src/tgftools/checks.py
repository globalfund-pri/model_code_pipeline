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

"""This file holds everything needed for the DatabaseChecks class."""


class DataCheckError(Exception):
    pass


@dataclass
class CheckResult:
    """DataClass for result of a single check"""

    passes: bool = None
    message: [
        str,
        matplotlib.figure.Figure,
        list[str],
        list[matplotlib.figure.Figure],
    ] = None


@dataclass
class CheckReport:
    """DataClass for report to be saved from having run a single check"""

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
    """Decorator used to signify that a particular check is a 'critical'."""

    @wraps(func)
    def wrapped(*args, **kwargs):
        return func(*args, **kwargs)

    wrapped.critical = True
    return wrapped


def is_critical(func):
    """Returns True if the function has been decorated as `@critical`.
    From: https://stackoverflow.com/a/68583930"""
    return getattr(func, "critical", False)


class DatabaseChecks:
    """This is the base class for the DatabaseChecks.
    The functions defined in the base class do the "behind the scenes" things needed to make the inherited class work.

    Each function defined in the inheriting class is a check to be performed on the Database. The name of the function
     should be informative and the docstring should explain exactly what is being tested. In the check, `assert` is
     used to indicate what must be True for the check to pass; and an error message is provided giving information
     if it does not. The `@critical` decorator is used to label certain of the checks as being 'critical'. A different
     overall message is given according to whether there are any failure of 'critical' checks or only failures of
     'non-critical' checks.
    """

    def __init__(self, db: Database, parameters: Optional[Parameters] = None):
        self.db = db
        self.parameters = parameters
        self.ccr = ConsolidatedChecksReport(
            title=type(self).__name__,
            doc=str(self.__doc__).replace("\n", ""),
            filenames={
                "Model Results": str(self.db.model_results.path),
                "Partner Data": "", #str(self.db.partner_data.path),
                "PF Input Data": "", #str(self.db.pf_input_data.path),
            },
        )

    def _run_check(self, the_func: Callable) -> CheckReport:
        """Run a particular check and return a Check Result.
        * A `CheckResult` instance should be returned by each check, giving the result of the check and a message
        * If nothing is returned, the check is assumed to have passed.
        * If an AssertionError occurs in the test, then it is assumed the check has failed and the message in the error
          is used as the message in the check.
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
        """Run all the checks that are defined in this class and returns True if all checks pass.
        A summary of the checks is printed to console. By default, any failed checks lead to an Error, but this can be
         stopped with `suppress_error`. Optionally, the results of the checks can be saved to a logfile.
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
        """Return the names of the checks found in the class.
        (A check is any function defined in the class where the name is not `run` or begins with `_`.)
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

    # def my_check(self, db: Database) -> CheckResult:
    #     """This is an example of a check. This docstring is the description of what the check does and is captured in
    #     the outputs.
    #     Each check should interrogate the database (`db`) and return an instance of `CheckResult`
    #      indicating whether the check has passed and (optionally) an accompanying message, which can be a
    #      string, a matplotlib figure or a pandas dataframe, or a list of these."""
    #     return CheckResult(passes=True, message='')


class ConsolidatedChecksReport:
    """This class is used to capture the reports from individual checks and compile them into a consolidated report,
    which is printed to the console and written to a pdf."""

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
        """Add the result of a check"""

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
        return [rep for rep in self._check_reports if rep.passes]

    @property
    def non_critical_failing_checks(self) -> List:
        return [
            rep for rep in self._check_reports if not rep.passes and not rep.is_critical
        ]

    @property
    def critical_failing_checks(self) -> List:
        return [
            rep for rep in self._check_reports if not rep.passes and rep.is_critical
        ]

    @property
    def any_fails(self) -> Bool:
        return any(self.critical_failing_checks) or any(
            self.non_critical_failing_checks
        )

    def _print(self, item, style=None, echo_to_console=True) -> None:
        """Print to console and add into a 'flowables' list for pdf generation."""

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
        """Generate the content of a report (for console and pdf)."""
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
        """Print a consolidated report the console. If `verbose=True` then details of all the failures are provided."""
        self._generate_report(verbose=verbose)

        if filename is not None:
            print(f"Writing to pdf at: {filename}: ....", end="")
            doc = SimpleDocTemplate(str(filename), pageSize=reportlab.lib.pagesizes.A4)
            doc.build(self.flowables)
            print("Done!")
