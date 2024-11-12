import pandas

from scripts.ic8.malaria.malaria_filehandlers import MALARIAMixin, PFInputDataMalaria, PartnerDataMalaria
from scripts.ic8.malaria.malaria_filehandlers import ModelResultsMalaria
from tgftools.database import Database
from tgftools.filehandler import Parameters, GFYear
from tgftools.utils import get_data_path, get_root_path, save_var, load_var

""" When running the resource need make sure to go to the parameter.toml file and select the second modelled country "
 "list under each disease, where there is a second list. This list matches modelled countries to countries for which "
 "we have health finance data, so we can compute a comparable resource need estimate.  """


class DatabaseChecksMalaria(MALARIAMixin,):
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
        path_to_data_folder / "IC8/modelling_outputs/malaria/2024_11_04",
        parameters=parameters,
    )

    # Load the files
    pf_input_data = PFInputDataMalaria(
        path_to_data_folder / "IC8/pf/malaria/2024_03_28",
        parameters=parameters,
    )

    partner_data = PartnerDataMalaria(
        path_to_data_folder / "IC8/partner/malaria/2024_10_17",
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
    cost_vx_by_year = cost_vx_by_year.rename(columns={'central': 'costvx_lb', 'high': 'costvx_ub', 'low': 'costvx_lb'})

    cost_priv_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'costtxprivate')
    ]
    cost_priv_df = cost_priv_df.reset_index()
    cost_priv_by_year = cost_priv_df.groupby('year').sum()
    del cost_priv_by_year['country']
    cost_priv_by_year = cost_priv_by_year.rename(columns={'central': 'costpriv_lb', 'high': 'costpriv_ub', 'low': 'costpriv_lb'})

    cases_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'cases')
    ]
    deaths_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'deaths')
    ]
    par_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'par')
    ]

    cases_df = cases_df.reset_index()
    cases_by_year = cases_df.groupby('year').sum()
    del cases_by_year['country']

    deaths_df = deaths_df.reset_index()
    deaths_by_year = deaths_df.groupby('year').sum()
    del deaths_by_year['country']

    par_df = par_df.reset_index()
    par_by_year = par_df.groupby('year').sum()
    del par_by_year['country']

    incidence_by_year = cases_by_year / par_by_year
    mortality_by_year = deaths_by_year / par_by_year

    incidence_by_year = incidence_by_year.rename(columns={'central': 'incidence', 'high': 'incidence_ub', 'low': 'incidence_lb'})
    mortality_by_year = mortality_by_year.rename(
        columns={'central': 'mortality', 'high': 'mortality_ub', 'low': 'mortality_lb'})

    # Merge all into one and save the output
    df_resource_need = pandas.concat([cost_by_year, cost_vx_by_year, cost_priv_by_year, incidence_by_year, mortality_by_year], axis=1)
    df_resource_need.to_csv('df_pf_100_malaria.csv')


    # Get data from partner data
    elig_countries = parameters.get_portfolio_countries_for('MALARIA')
    cases_df_hh = partner_data.df.loc[
        (slice(None), elig_countries, slice(None), 'cases')
    ]
    deaths_df_hh = partner_data.df.loc[
        (slice(None), elig_countries, slice(None), 'deaths')
    ]

    par_df_hh = partner_data.df.loc[
        (slice(None), elig_countries, slice(None), 'par')
    ]

    cases_df_hh = cases_df_hh.reset_index()
    cases_hh_by_year = cases_df_hh.groupby(['year'], as_index=True).sum()
    columns_to_drop = ['country', 'scenario_descriptor', 'indicator']
    cases_hh_by_year = cases_hh_by_year.drop(columns=columns_to_drop, axis=1)

    deaths_df_hh = deaths_df_hh.reset_index()
    deaths_hh_by_year = deaths_df_hh.groupby(['year'], as_index=True).sum()
    deaths_hh_by_year = deaths_hh_by_year.drop(columns=columns_to_drop, axis=1)

    par_df_hh = par_df_hh.reset_index()
    par_hh_by_year = par_df_hh.groupby(['year'], as_index=True).sum()
    par_hh_by_year = par_hh_by_year.drop(columns=columns_to_drop, axis=1)

    incidence_hh_by_year = cases_hh_by_year / par_hh_by_year
    mortality_hh_by_year = deaths_hh_by_year / par_hh_by_year

    incidence_hh_by_year = incidence_hh_by_year.rename(
        columns={'central': 'incidence', 'high': 'incidence_ub', 'low': 'incidence_lb'})
    mortality_hh_by_year = mortality_hh_by_year.rename(
        columns={'central': 'mortality', 'high': 'mortality_ub', 'low': 'mortality_lb'})

    # Merge all into one and save the output
    df_resource_need = pandas.concat(
        [incidence_hh_by_year, mortality_hh_by_year], axis=1)
    df_resource_need.to_csv('df_partner_malaria.csv')


