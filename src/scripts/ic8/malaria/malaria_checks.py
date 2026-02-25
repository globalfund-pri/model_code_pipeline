from scripts.ic8.malaria.malaria_filehandlers import MALARIAMixin, PFInputDataMalaria, PartnerDataMalaria, GpMalaria
from scripts.ic8.shared.common_checks import (CommonChecks_basicnumericalchecks,
                                              CommonChecks_allscenarios,
                                              CommonChecks_forwardchecks)
from scripts.ic8.malaria.malaria_filehandlers import ModelResultsMalaria
from tgftools.FilePaths import FilePaths
from tgftools.checks import DatabaseChecks
from tgftools.database import Database
from tgftools.filehandler import Parameters, FixedGp
from tgftools.utils import get_root_path

"""Performs validation checks on malaria model data and generates a report.

This module runs comprehensive data quality checks on malaria modeling outputs
and saves the results as a PDF report.

Notes:
    Given the format of the model data, funding fractions had to be coded
    differently for the checks compared to the analysis for HIV and TB. This is
    not the case for malaria.

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


class DatabaseChecksMalaria(MALARIAMixin,
                            CommonChecks_basicnumericalchecks,
                            CommonChecks_allscenarios,
                            CommonChecks_forwardchecks,
                            DatabaseChecks):
    """Performs database validation checks specific to malaria data.

    This class combines malaria-specific mixins with common check classes to
    validate malaria model data. It inherits from multiple check classes to
    provide comprehensive data quality validation.

    Attributes:
        Inherited from parent classes including MALARIAMixin,
        CommonChecks_basicnumericalchecks, CommonChecks_allscenarios,
        CommonChecks_forwardchecks, and DatabaseChecks.
    """

    def __init__(self, *args, **kwargs):
        """Initializes the DatabaseChecksMalaria instance.

        Args:
            *args: Variable length argument list passed to parent classes.
            **kwargs: Arbitrary keyword arguments passed to parent classes.
        """
        super().__init__(*args, **kwargs)


if __name__ == "__main__":
    # Declare the parameters and filepaths
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    # Load the files
    model_results = ModelResultsMalaria(
        filepaths.get('malaria', 'model-results'),
        parameters=parameters,
    )

    # Load the files
    pf_input_data = PFInputDataMalaria(
        filepaths.get('malaria', 'pf-input-data'),
        parameters=parameters,
    )

    partner_data = PartnerDataMalaria(
        filepaths.get('malaria', 'partner-data'),
        parameters=parameters,
    )

    fixed_gp = FixedGp(
        filepaths.get('malaria', 'gp-data'),
        parameters=parameters,
    )

    # This calls the code that generates the milestone based GP
    gp = GpMalaria(
        fixed_gp=fixed_gp,
        model_results=model_results,
        partner_data=partner_data,
        parameters=parameters,
    )

    # Create the database
    db = Database(
        model_results=model_results,
        gp=gp,
        pf_input_data=pf_input_data,
        partner_data=partner_data,
    )

    # Run the checks
    DatabaseChecksMalaria(
        db=db,
        parameters=parameters,
    ).run(
        suppress_error=True,
        filename=project_root / "outputs" / "malaria_report_of_checks.pdf"
    )
