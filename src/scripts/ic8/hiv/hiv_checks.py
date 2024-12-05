import pandas

from scripts.ic8.hiv.hiv_filehandlers import HIVMixin, PFInputDataHIV, PartnerDataHIV
from scripts.ic8.shared.common_checks import CommonChecks_basicnumericalchecks, CommonChecks_allscenarios, CommonChecks_forwardchecks
from scripts.ic8.hiv.hiv_filehandlers import ModelResultsHiv
from tgftools.FilePaths import FilePaths
from tgftools.checks import DatabaseChecks
from tgftools.database import Database
from tgftools.filehandler import Parameters, GFYear
from tgftools.utils import get_data_path, get_root_path


class DatabaseChecksHiv(HIVMixin, CommonChecks_basicnumericalchecks, CommonChecks_allscenarios, CommonChecks_forwardchecks, DatabaseChecks):
    """This is the class for DatabaseChecks to do with the HIV data."""

    def __init__(self, *args, **kwargs):
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

    # fixed_gp = FixedGp(
    #     filepaths.get('hiv', 'gp-data'),
    #     parameters=parameters,
    # )

    # Create the database
    db = Database(
        model_results=model_results,
        # gp=gp,
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