from scripts.ic8.hiv.hiv_filehandlers import HIVMixin, PFInputDataHIV, PartnerDataHIV, GpHiv
from scripts.ic8.shared.common_checks import (CommonChecks_basicnumericalchecks,
                                              CommonChecks_allscenarios,
                                              CommonChecks_forwardchecks)
from scripts.ic8.hiv.hiv_filehandlers import ModelResultsHiv
from tgftools.FilePaths import FilePaths
from tgftools.checks import DatabaseChecks
from tgftools.database import Database
from tgftools.filehandler import Parameters, FixedGp
from tgftools.utils import get_root_path

"""Performs validation checks on HIV model data and generates a report.

This module runs comprehensive data quality checks on HIV modeling outputs
and saves the results as a PDF report.

Notes:
    Given the format of the model data, funding fractions are coded differently
    for checks compared to analysis. It is recommended that checks are run from
    these scripts.

    To perform the checks and account for funding fractions, go to each
    disease-specific filehandler and ensure that in the class (e.g.,
    ModelResultsHiv(HIVMixin, ModelResults)) the checks are set to 1. There
    should be two instances in HIV, one in TB, and none in malaria. You can
    search for "check = ".

Configuration:
    All parameters and files defining this analysis are set out in the
    following two files:
    - parameters.toml: Outlines key parameters for the analysis, list of
      scenarios and how they are mapped compared to CC, NULL, and GP, the list
      of modeled and portfolio countries to run, and the list of variables and
      how these should be handled (scaled to portfolio or not).
    - filepaths.toml: Specifies which model data and funding data to be used
      for this analysis.
"""


class DatabaseChecksHiv(HIVMixin,
                        CommonChecks_basicnumericalchecks,
                        CommonChecks_allscenarios,
                        CommonChecks_forwardchecks,
                        DatabaseChecks):
    """Performs database validation checks specific to HIV data.

    This class combines HIV-specific mixins with common check classes to validate
    HIV model data. It inherits from multiple check classes to provide comprehensive
    data quality validation.

    Attributes:
        Inherited from parent classes including HIVMixin, CommonChecks_basicnumericalchecks,
        CommonChecks_allscenarios, CommonChecks_forwardchecks, and DatabaseChecks.
    """

    def __init__(self, *args, **kwargs):
        """Initializes the DatabaseChecksHiv instance.

        Args:
            *args: Variable length argument list passed to parent classes.
            **kwargs: Arbitrary keyword arguments passed to parent classes.
        """
        super().__init__(*args, **kwargs)


if __name__ == "__main__":
    project_root = get_root_path()
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    # Declare the parameters, indicators and scenarios
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")

    # Load the files
    model_results = ModelResultsHiv(
        filepaths.get('hiv', 'model-results'),
        parameters=parameters,
    )

    # Load the files
    pf_input_data = PFInputDataHIV(
        filepaths.get('hiv', 'pf-input-data'),
        parameters=parameters,
    )

    partner_data = PartnerDataHIV(
        filepaths.get('hiv', 'partner-data'),
        parameters=parameters,
    )

    fixed_gp = FixedGp(
        filepaths.get('hiv', 'gp-data'),
        parameters=parameters,
    )

    # This calls the code that generates the milestone based GP, even if we do not have one for HIV
    gp = GpHiv(
        fixed_gp=fixed_gp,
        model_results=model_results,
        partner_data=partner_data,
        parameters=parameters
    )

    # Create the database
    db = Database(
        model_results=model_results,
        gp=gp,
        pf_input_data=pf_input_data,
        partner_data=partner_data,
    )

    # Run the checks
    DatabaseChecksHiv(
        db=db,
        parameters=parameters,
    ).run(
        suppress_error=True,
        filename=project_root / "outputs" / "hiv_report_of_checks.pdf"
    )
