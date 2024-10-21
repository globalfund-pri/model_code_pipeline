import pandas

from scripts.ic8.tb.tb_filehandlers import TBMixin, PFInputDataTb, PartnerDataTb
from scripts.ic8.tb.tb_filehandlers import ModelResultsTb
from tgftools.database import Database
from tgftools.filehandler import Parameters, GFYear
from tgftools.utils import get_data_path, get_root_path


class DatabaseChecksTb(TBMixin, ):
    """This is the class for DatabaseChecks to do with the Tb data."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


if __name__ == "__main__":

    path_to_data_folder = get_data_path()
    project_root = get_root_path()

    # Declare the parameters, indicators and scenarios
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")

    # Load the files
    model_results = ModelResultsTb(
        path_to_data_folder / "IC8/modelling_outputs/tb/2024_09_04",
        parameters=parameters,
    )

    # Load the files
    pf_input_data = PFInputDataTb(
        path_to_data_folder / "IC8/pf/tb/2024_03_28",
        parameters=parameters,
    )

    partner_data = PartnerDataTb(
        path_to_data_folder / "IC8/partner/tb/2024_10_17",
        parameters=parameters,
    )


    # Create the database
    db = Database(
        model_results=model_results,
        pf_input_data=pf_input_data,
        partner_data=partner_data,
    )

    # Save output for Nick Menzies
    fuc_mainscenario_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), slice(None))
    ]
    fuc_mainscenario_df = fuc_mainscenario_df.reset_index()
    fuc_mainscenario_df['scenario_descriptor'] = "PF_100"

    fuc_cc2022_df = model_results.df.loc[
        ("CC_2022", 1, slice(None), slice(None), slice(None))
    ]
    fuc_cc2022_df = fuc_cc2022_df.reset_index()
    fuc_cc2022_df['scenario_descriptor'] = "CC_2022"

    fuc_null2022_df = model_results.df.loc[
        ("NULL_2022", 1, slice(None), slice(None), slice(None))
    ]
    fuc_null2022_df = fuc_null2022_df.reset_index()
    fuc_null2022_df['scenario_descriptor'] = "NULL_2022"

    fuc_df = pandas.concat(
        [fuc_mainscenario_df, fuc_cc2022_df, fuc_null2022_df], axis=0)

    # Save output
    fuc_df.to_csv('df_freed_up_capacity_tb.csv')