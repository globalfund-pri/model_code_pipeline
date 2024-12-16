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

"""
This script performs the checks and saves the output as a report.

NOTES: Given the format of the model data, the funding fractions had to be coded up differently for the checks compared 
to the analysis. As such it is recommended that checks are run from these scripts. 

To perform the checks and to account for the above point on funding fractions go to each disease-specific filehandler
and ensure that in the class e.g. ModelResultsHiv(HIVMixin, ModelResults) the checks are set to 1. There should be two 
instances in hiv, one in tb and none in malaria. You can search for "check = ".  

All parameters and files defining this analysis are set out in the following two files: 
- The parameters.toml file, which outlines all the key parameters outlining the analysis, list of scenarios and how they 
  are mapped compared to cc, null and gp, the list of modelled and portfolio countries to run as well as the list of the 
  variables and how these should be handled (scaled to portfolio or not).
- The filepaths.toml, which outlines which model data and funding data to be used for this analysis.  
"""


class DatabaseChecksHiv(HIVMixin,
                        CommonChecks_basicnumericalchecks,
                        CommonChecks_allscenarios,
                        CommonChecks_forwardchecks,
                        DatabaseChecks):
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
