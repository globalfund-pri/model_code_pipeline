import pandas

from scripts.ic8.malaria.malaria_filehandlers import MALARIAMixin, PFInputDataMalaria, PartnerDataMalaria
from scripts.ic8.shared.common_checks import CommonChecks_basicnumericalchecks, CommonChecks_allscenarios, CommonChecks_forwardchecks
from scripts.ic8.malaria.malaria_filehandlers import ModelResultsMalaria
from tgftools.FilePaths import FilePaths
from tgftools.checks import DatabaseChecks
from tgftools.database import Database
from tgftools.filehandler import Parameters, GFYear
from tgftools.utils import get_data_path, get_root_path, save_var, load_var


class DatabaseChecksMalaria(MALARIAMixin,
                            CommonChecks_basicnumericalchecks,
                            CommonChecks_allscenarios,
                            CommonChecks_forwardchecks,
                            DatabaseChecks):
    """This is the class for DatabaseChecks to do with the Malaria data."""

    def __init__(self, *args, **kwargs):
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

    # fixed_gp = FixedGp(
    #     filepaths.get('malaria', 'gp-data'),
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
    DatabaseChecksMalaria(
        db=db,
        parameters=parameters,
    ).run(
        suppress_error=True,
        filename=project_root / "outputs" / "malaria_report_of_checks.pdf"
    )