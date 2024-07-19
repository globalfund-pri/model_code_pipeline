from scripts.ic8.malaria.malaria_filehandlers import MALARIAMixin
from scripts.ic8.shared.common_checks import CommonChecks_basicnumericalchecks, CommonChecks_allscenarios
from scripts.ic8.malaria.malaria_filehandlers import ModelResultsMalaria
from tgftools.checks import DatabaseChecks
from tgftools.database import Database
from tgftools.filehandler import Parameters, GFYear
from tgftools.utils import get_data_path, get_root_path


class DatabaseChecksMalaria(MALARIAMixin, CommonChecks_basicnumericalchecks, CommonChecks_allscenarios, DatabaseChecks):
    """This is the class for DatabaseChecks to do with the Malaria data."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

if __name__ == "__main__":

    path_to_data_folder = get_data_path()
    project_root = get_root_path()

    # Declare the parameters, indicators and scenarios
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")

    # Load the files
    model_results = ModelResultsMalaria(
        path_to_data_folder / "IC8/modelling_outputs/malaria/2024_7_11",
        parameters=parameters,
    )

    # Load the files
    # pf_input_data = PFInputDataMalaria(
    #     path_to_data_folder / "IC8/pf/malaria",
    #     parameters=parameters,
    # )

    # partner_data = PartnerDataHIV(
    #     path_to_data_folder / "IC8/partner/hiv",
    #     parameters=parameters,
    # )

    # fixed_gp = FixedGp(
    #     get_root_path() / "src" / "scripts" / "IC7" / "shared" / "fixed_gps" / "hiv_gp.csv",
    #     parameters=parameters,
    # )

    # Create the database
    db = Database(
        model_results=model_results,
        # gp=gp,
        # pf_input_data=pf_input_data,
        # partner_data=partner_data,
    )

    # Run the checks
    DatabaseChecksMalaria(
        db=db,
        parameters=parameters,
    ).run(
        suppress_error=True,
        filename=project_root / "outputs" / "ic8" / "malaria_report_of_checks.pdf"
    )
