import pandas

from scripts.ic8.malaria.malaria_filehandlers import MALARIAMixin, PFInputDataMalaria, PartnerDataMalaria
from scripts.ic8.malaria.malaria_filehandlers import ModelResultsMalaria
from tgftools.FilePaths import FilePaths
from tgftools.database import Database
from tgftools.filehandler import Parameters
from tgftools.utils import get_root_path

"""
This is a simple piece of code that utilizes the Database check to extract dummy data for the freed up capacity. 
This code is not part of the modular framework. 
"""


class DatabaseChecksMalaria(MALARIAMixin, ):
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

    # Create the database
    db = Database(
        model_results=model_results,
        pf_input_data=pf_input_data,
        partner_data=partner_data,
    )

    # Save output for Nick Menzies
    list_of_scenarios = ["HH", "NULL_2000", "CC_2000", "NULL_2022", "CC_2022"]
    fuc_mainscenario_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), slice(None))
    ]
    fuc_mainscenario_df = fuc_mainscenario_df.reset_index()
    fuc_mainscenario_df['scenario_descriptor'] = "PF_100"

    fuc_cf_df = model_results.df.loc[
        (list_of_scenarios, 1, slice(None), slice(None), slice(None))
    ]
    fuc_cf_df = fuc_cf_df.reset_index()

    fuc_df = pandas.concat(
        [fuc_mainscenario_df, fuc_cf_df], axis=0)

    fuc_df = fuc_df.drop(columns=["funding_fraction"])

    # Save output
    fuc_df.to_csv('df_ic_data_malaria.csv')
