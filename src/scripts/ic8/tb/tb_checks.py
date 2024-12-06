import pandas

from scripts.ic8.tb.tb_filehandlers import TBMixin, PFInputDataTb, PartnerDataTb, GpTb
from scripts.ic8.shared.common_checks import (CommonChecks_basicnumericalchecks,
                                              CommonChecks_allscenarios,
                                              CommonChecks_forwardchecks)
from scripts.ic8.tb.tb_filehandlers import ModelResultsTb
from tgftools.FilePaths import FilePaths
from tgftools.checks import DatabaseChecks
from tgftools.database import Database
from tgftools.filehandler import Parameters, FixedGp
from tgftools.utils import get_root_path

"""
This script specifies the parameter file and filepath file, loads all the data and runs the checks. 
"""

class DatabaseChecksTb(TBMixin,
                       CommonChecks_basicnumericalchecks,
                       CommonChecks_allscenarios,
                       CommonChecks_forwardchecks,
                       DatabaseChecks):
    """This is the class for DatabaseChecks to do with the Tb data."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


if __name__ == "__main__":

    # Declare the parameters and filepaths
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    # Load the files
    model_results = ModelResultsTb(
        filepaths.get('tb', 'model-results'),
        parameters=parameters,
    )

    # Load the files
    pf_input_data = PFInputDataTb(
        filepaths.get('tb', 'pf-input-data'),
        parameters=parameters,
    )

    partner_data = PartnerDataTb(
        filepaths.get('tb', 'partner-data'),
        parameters=parameters,
    )

    fixed_gp = FixedGp(
        filepaths.get('tb', 'gp-data'),
        parameters=parameters,
    )

    # This calls the code that generates the milestone based GP
    gp = GpTb(
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
    DatabaseChecksTb(
        db=db,
        parameters=parameters,
    ).run(
        suppress_error=True,
        filename=project_root / "outputs" / "tb_report_of_checks.pdf"
    )
