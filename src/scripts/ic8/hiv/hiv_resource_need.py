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
        path_to_data_folder / "IC8/modelling_outputs/hiv/2024_09_25",
        parameters=parameters,
    )

    # Load the files
    pf_input_data = PFInputDataHIV(
        path_to_data_folder / "IC8/pf/hiv/2024_03_28",
        parameters=parameters,
    )

    partner_data = PartnerDataHIV(
        path_to_data_folder / "IC8/partner/hiv/2024_07_10",
        parameters=parameters,
    )

    # Create the database
    db = Database(
        model_results=model_results,
        pf_input_data=pf_input_data,
        partner_data=partner_data,
    )

    # Run new resource need:
    cost_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'cost')
    ]
    cost_df = cost_df.reset_index()
    cost_by_year = cost_df.groupby('year').sum()
    del cost_by_year['country']
    cost_by_year = cost_by_year.rename(columns={'central': 'cost', 'high': 'cost_ub', 'low': 'cost_lb'})

    cases_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'cases')
    ]
    deaths_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'deaths')
    ]
    plhiv_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'plhiv')
    ]
    hivneg_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'hivneg')
    ]

    cases_df = cases_df.reset_index()
    cases_by_year = cases_df.groupby('year').sum()
    del cases_by_year['country']

    deaths_df = deaths_df.reset_index()
    deaths_by_year = deaths_df.groupby('year').sum()
    del deaths_by_year['country']

    plhiv_df = plhiv_df.reset_index()
    plhiv_by_year = plhiv_df.groupby('year').sum()
    del plhiv_by_year['country']

    hivneg_df = hivneg_df.reset_index()
    hivneg_by_year = hivneg_df.groupby('year').sum()
    del hivneg_by_year['country']

    incidence_by_year = cases_by_year / hivneg_by_year
    mortality_by_year = deaths_by_year / plhiv_by_year

    incidence_by_year = incidence_by_year.rename(
        columns={'central': 'incidence', 'high': 'incidence_ub', 'low': 'incidence_lb'})
    mortality_by_year = mortality_by_year.rename(
        columns={'central': 'mortality', 'high': 'mortality_ub', 'low': 'mortality_lb'})

    # Merge all into one and save the output
    df_resource_need = pandas.concat(
        [cost_by_year, incidence_by_year, mortality_by_year], axis=1)
    df_resource_need.to_csv('df_resource_need_hiv.csv')



