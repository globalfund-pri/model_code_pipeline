import pandas

from scripts.ic8.hiv.hiv_filehandlers import HIVMixin, PFInputDataHIV, PartnerDataHIV
from scripts.ic8.hiv.hiv_filehandlers import ModelResultsHiv
from tgftools.database import Database
from tgftools.filehandler import Parameters, GFYear
from tgftools.utils import get_data_path, get_root_path


class DatabaseChecksHiv(HIVMixin,):
    """This is the class for DatabaseChecks to do with the HIV data."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


if __name__ == "__main__":

    path_to_data_folder = get_data_path()
    project_root = get_root_path()

    # Declare the parameters, indicators and scenarios
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")

    # Load the files
    model_results = ModelResultsHiv(
        path_to_data_folder / "IC8/modelling_outputs/hiv/2024_10_15",
        parameters=parameters,
    )

    # Load the files
    pf_input_data = PFInputDataHIV(
        path_to_data_folder / "IC8/pf/hiv/2024_03_28",
        parameters=parameters,
    )

    partner_data = PartnerDataHIV(
        path_to_data_folder / "IC8/partner/hiv/2024_10_17",
        parameters=parameters,
    )

    # Create the database
    db = Database(
        model_results=model_results,
        pf_input_data=pf_input_data,
        partner_data=partner_data,
    )

    # Save output for Nick Menzies
    list_of_hh_scenarios = ["HH", "NULL_2000", "CC_2000"]
    list_of_fw_scenarios = ["NULL_2022", "CC_2022"]
    fuc_mainscenario_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), slice(None))
    ]
    fuc_mainscenario_df = fuc_mainscenario_df.reset_index()
    fuc_mainscenario_df['scenario_descriptor'] = "PF_100"

    fuc_cf_fw_df = model_results.df.loc[
        (list_of_fw_scenarios, 1, slice(None), slice(None), slice(None))
    ]
    fuc_cf_fw_df = fuc_cf_fw_df.reset_index()

    fuc_cf_hh_df = model_results.df.loc[
        (list_of_hh_scenarios, 1, slice(None), slice(None), slice(None))
    ]
    fuc_cf_hh_df = fuc_cf_hh_df.reset_index()

    fuc_df = pandas.concat(
        [fuc_mainscenario_df, fuc_cf_fw_df, fuc_cf_hh_df], axis=0)

    fuc_df = fuc_df.drop(columns=["funding_fraction"])

    # Save output
    fuc_df.to_csv('df_ic_data_hiv.csv')