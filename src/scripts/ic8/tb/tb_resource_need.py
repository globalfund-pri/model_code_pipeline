import pandas

from scripts.ic8.tb.tb_filehandlers import TBMixin, PFInputDataTb, PartnerDataTb
from scripts.ic8.tb.tb_filehandlers import ModelResultsTb
from tgftools.database import Database
from tgftools.filehandler import Parameters, GFYear
from tgftools.utils import get_data_path, get_root_path

""" When running the resource need make sure to go to the parameter.toml file and select the second modelled country "
 "list under each disease, where there is a second list. This list matches modelled countries to countries for which "
 "we have health finance data, so we can compute a comparable resource need estimate.  """


class DatabaseChecksTb(TBMixin,):
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
        path_to_data_folder / "IC8/modelling_outputs/tb/2024_10_15",
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

    # Run new resource need:
    cost_df = model_results.df.loc[
            ("PF", 1, slice(None), slice(None), 'cost')
        ]
    cost_df = cost_df.reset_index()
    cost_by_year = cost_df.groupby('year').sum()
    del cost_by_year['country']
    cost_by_year = cost_by_year.rename(columns={'central': 'cost', 'high': 'cost_ub', 'low': 'cost_lb'})

    cost_vx_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'costvx')
    ]
    cost_vx_df = cost_vx_df.reset_index()
    cost_vx_by_year = cost_vx_df.groupby('year').sum()
    del cost_vx_by_year['country']
    cost_vx_by_year = cost_vx_by_year.rename(columns={'central': 'costvx', 'high': 'costvx_ub', 'low': 'costvx_lb'})

    # Forward-looking epi
    cases_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'cases')
    ]
    deaths_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'deaths')
    ]
    pop_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'population')
    ]

    cases_df = cases_df.reset_index()
    cases_by_year = cases_df.groupby('year').sum()
    del cases_by_year['country']

    deaths_df = deaths_df.reset_index()
    deaths_by_year = deaths_df.groupby('year').sum()
    del deaths_by_year['country']

    pop_df = pop_df.reset_index()
    pop_by_year = pop_df.groupby('year').sum()
    del pop_by_year['country']

    incidence_by_year = cases_by_year / pop_by_year
    mortality_by_year = deaths_by_year / pop_by_year

    incidence_by_year = incidence_by_year.rename(columns={'central': 'incidence', 'high': 'incidence_ub', 'low': 'incidence_lb'})
    mortality_by_year = mortality_by_year.rename(
        columns={'central': 'mortality', 'high': 'mortality_ub', 'low': 'mortality_lb'})

    # Historic epidemic
    cases_df_hh = model_results.df.loc[
        ("HH", 1, slice(None), slice(None), 'cases')
    ]
    deaths_df_hh = model_results.df.loc[
        ("HH", 1, slice(None), slice(None), 'deaths')
    ]
    pop_df_hh = model_results.df.loc[
        ("HH", 1, slice(None), slice(None), 'population')
    ]

    cases_df_hh = cases_df_hh.reset_index()
    cases_hh_by_year = cases_df_hh.groupby('year').sum()
    del cases_hh_by_year['country']

    deaths_df_hh = deaths_df_hh.reset_index()
    deaths_hh_by_year = deaths_df_hh.groupby('year').sum()
    del deaths_hh_by_year['country']

    pop_df_hh = pop_df_hh.reset_index()
    pop_hh_by_year = pop_df_hh.groupby('year').sum()
    del pop_hh_by_year['country']

    incidence_hh_by_year = cases_hh_by_year / pop_hh_by_year
    mortality_hh_by_year = deaths_hh_by_year / pop_hh_by_year

    incidence_hh_by_year = incidence_hh_by_year.rename(
        columns={'central': 'incidence', 'high': 'incidence_ub', 'low': 'incidence_lb'})
    mortality_hh_by_year = mortality_hh_by_year.rename(
        columns={'central': 'mortality', 'high': 'mortality_ub', 'low': 'mortality_lb'})

    # Concat epi
    incidence_by_year = pandas.concat([incidence_hh_by_year, incidence_by_year])
    mortality_by_year = pandas.concat([mortality_hh_by_year, mortality_by_year])

    # Merge all into one and save the output
    df_costs = pandas.concat([cost_by_year, cost_vx_by_year], axis=1)
    df_costs = df_costs.reset_index()
    df_epi = pandas.concat([incidence_by_year, mortality_by_year], axis=1)
    df_epi = df_epi.reset_index()

    df_resource_need = (pandas.merge(df_epi, df_costs, on='year', how = 'outer'))
    df_resource_need.to_csv('df_resource_need_tb.csv')




    # Run new resource need for GP:
    cost_df = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'cost')
    ]
    cost_df = cost_df.reset_index()
    cost_by_year = cost_df.groupby('year').sum()
    del cost_by_year['country']
    cost_by_year = cost_by_year.rename(columns={'central': 'cost', 'high': 'cost_ub', 'low': 'cost_lb'})

    cost_vx_df = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'costvx')
    ]
    cost_vx_df = cost_vx_df.reset_index()
    cost_vx_by_year = cost_vx_df.groupby('year').sum()
    del cost_vx_by_year['country']
    cost_vx_by_year = cost_vx_by_year.rename(columns={'central': 'costvx', 'high': 'costvx_ub', 'low': 'costvx_lb'})

    # Forward-looking epi
    cases_df = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'cases')
    ]
    deaths_df = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'deaths')
    ]
    pop_df = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'population')
    ]

    cases_df = cases_df.reset_index()
    cases_by_year = cases_df.groupby('year').sum()
    del cases_by_year['country']

    deaths_df = deaths_df.reset_index()
    deaths_by_year = deaths_df.groupby('year').sum()
    del deaths_by_year['country']

    pop_df = pop_df.reset_index()
    pop_by_year = pop_df.groupby('year').sum()
    del pop_by_year['country']

    incidence_by_year = cases_by_year / pop_by_year
    mortality_by_year = deaths_by_year / pop_by_year

    incidence_by_year = incidence_by_year.rename(
        columns={'central': 'incidence', 'high': 'incidence_ub', 'low': 'incidence_lb'})
    mortality_by_year = mortality_by_year.rename(
        columns={'central': 'mortality', 'high': 'mortality_ub', 'low': 'mortality_lb'})

    df_resource_need = (pandas.merge(incidence_by_year, mortality_by_year, on='year', how='outer'))
    df_resource_need.to_csv('df_resource_need_tb_gp.csv')

