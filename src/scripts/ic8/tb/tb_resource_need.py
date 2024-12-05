import pandas

from scripts.ic8.tb.tb_filehandlers import TBMixin, PFInputDataTb, PartnerDataTb
from scripts.ic8.tb.tb_filehandlers import ModelResultsTb
from tgftools.FilePaths import FilePaths
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

    # Create the database
    db = Database(
        model_results=model_results,
        pf_input_data=pf_input_data,
        partner_data=partner_data,
    )

    # Run data from PF scenario:
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

    cases_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'cases')
    ]
    deaths_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'deaths')
    ]
    deathshivneg_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'deathshivneg')
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

    deathshivneg_df = deathshivneg_df.reset_index()
    deathshivneg_by_year = deathshivneg_df.groupby('year').sum()
    del deathshivneg_by_year['country']

    pop_df = pop_df.reset_index()
    pop_by_year = pop_df.groupby('year').sum()
    del pop_by_year['country']

    incidence_by_year = cases_by_year / pop_by_year
    mortality_by_year = deaths_by_year / pop_by_year
    mortalityhivneg_by_year = deathshivneg_by_year / pop_by_year

    incidence_by_year = incidence_by_year.rename(
        columns={'central': 'incidence', 'high': 'incidence_ub', 'low': 'incidence_lb'})
    mortality_by_year = mortality_by_year.rename(
        columns={'central': 'mortality', 'high': 'mortality_ub', 'low': 'mortality_lb'})
    mortalityhivneg_by_year = mortalityhivneg_by_year.rename(
        columns={'central': 'mortalityhivneg', 'high': 'mortalityhivneg_ub', 'low': 'mortalityhivneg_lb'})

    # Merge all into one and save the output
    df_resource_need = pandas.concat(
        [cost_by_year, incidence_by_year, mortality_by_year, mortalityhivneg_by_year, cases_by_year, deaths_by_year, deathshivneg_by_year, pop_by_year], axis=1)
    df_resource_need.to_csv('df_pf100_tb.csv')


    # Run data from GP scenario:
    cost_df_gp = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'cost')
    ]
    cost_df_gp = cost_df_gp.reset_index()
    cost_by_year_gp = cost_df_gp.groupby('year').sum()
    del cost_by_year_gp['country']
    cost_by_year_gp = cost_by_year_gp.rename(columns={'central': 'cost', 'high': 'cost_ub', 'low': 'cost_lb'})

    cost_vx_df_gp = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'costvx')
    ]
    cost_vx_df_gp = cost_vx_df_gp.reset_index()
    cost_vx_by_year_gp = cost_vx_df_gp.groupby('year').sum()
    del cost_vx_by_year_gp['country']
    cost_vx_by_year_gp = cost_vx_by_year_gp.rename(columns={'central': 'costvx', 'high': 'costvx_ub', 'low': 'costvx_lb'})

    cases_df_gp = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'cases')
    ]
    deaths_df_gp = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'deaths')
    ]
    deathshivneg_df_gp = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'deathshivneg')
    ]
    pop_df_gp = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'population')
    ]

    cases_df_gp = cases_df_gp.reset_index()
    cases_by_year_gp = cases_df_gp.groupby('year').sum()
    del cases_by_year_gp['country']

    deaths_df_gp = deaths_df_gp.reset_index()
    deaths_by_year_gp = deaths_df_gp.groupby('year').sum()
    del deaths_by_year_gp['country']

    deathshivneg_df_gp = deathshivneg_df_gp.reset_index()
    deathshivneg_by_year_gp = deathshivneg_df_gp.groupby('year').sum()
    del deathshivneg_by_year_gp['country']

    pop_df_gp = pop_df_gp.reset_index()
    pop_by_year_gp = pop_df_gp.groupby('year').sum()
    del pop_by_year_gp['country']

    incidence_by_year_gp = cases_by_year_gp / pop_by_year_gp
    mortality_by_year_gp = deaths_by_year_gp / pop_by_year_gp
    mortalityhivneg_by_year_gp = deathshivneg_by_year_gp / pop_by_year_gp

    incidence_by_year_gp = incidence_by_year_gp.rename(
        columns={'central': 'incidence', 'high': 'incidence_ub', 'low': 'incidence_lb'})
    mortality_by_year_gp = mortality_by_year_gp.rename(
        columns={'central': 'mortality', 'high': 'mortality_ub', 'low': 'mortality_lb'})
    mortalityhivneg_by_year_gp = mortalityhivneg_by_year_gp.rename(
        columns={'central': 'mortalityhivneg', 'high': 'mortalityhivneg_ub', 'low': 'mortalityhivneg_lb'})

    df_resource_need = pandas.concat(
        [incidence_by_year_gp, mortality_by_year_gp, mortalityhivneg_by_year_gp], axis=1)
    df_resource_need.to_csv('df_gp_tb.csv')


    # Get data from partner data
    elig_countries = parameters.get_portfolio_countries_for('TB')
    cases_df_hh = partner_data.df.loc[
        (slice(None), elig_countries, slice(None), 'cases')
    ]
    deaths_df_hh = partner_data.df.loc[
        (slice(None), elig_countries, slice(None), 'deaths')
    ]
    deathshivneg_df_hh = partner_data.df.loc[
        (slice(None), elig_countries, slice(None), 'deathshivneg')
    ]
    pop_df_hh = partner_data.df.loc[
        (slice(None), elig_countries, slice(None), 'population')
    ]

    cases_df_hh = cases_df_hh.reset_index()
    cases_hh_by_year = cases_df_hh.groupby(['year'], as_index=True).sum()
    columns_to_drop = ['country', 'scenario_descriptor', 'indicator']
    cases_hh_by_year = cases_hh_by_year.drop(columns=columns_to_drop, axis=1)

    deaths_df_hh = deaths_df_hh.reset_index()
    deaths_hh_by_year = deaths_df_hh.groupby(['year'], as_index=True).sum()
    deaths_hh_by_year = deaths_hh_by_year.drop(columns=columns_to_drop, axis=1)

    deathshivneg_df_hh = deathshivneg_df_hh.reset_index()
    deathshivneg_hh_by_year = deathshivneg_df_hh.groupby(['year'], as_index=True).sum()
    deathshivneg_hh_by_year = deathshivneg_hh_by_year.drop(columns=columns_to_drop, axis=1)

    pop_df_hh = pop_df_hh.reset_index()
    pop_hh_by_year = pop_df_hh.groupby(['year'], as_index=True).sum()
    pop_hh_by_year = pop_hh_by_year.drop(columns=columns_to_drop, axis=1)

    incidence_hh_by_year = cases_hh_by_year / pop_hh_by_year
    mortality_hh_by_year = deaths_hh_by_year / pop_hh_by_year
    mortalityhivneg_hh_by_year = deathshivneg_hh_by_year / pop_hh_by_year

    incidence_hh_by_year = incidence_hh_by_year.rename(
        columns={'central': 'incidence', 'high': 'incidence_ub', 'low': 'incidence_lb'})
    mortality_hh_by_year = mortality_hh_by_year.rename(
        columns={'central': 'mortality', 'high': 'mortality_ub', 'low': 'mortality_lb'})
    mortalityhivneg_hh_by_year = mortalityhivneg_hh_by_year.rename(
        columns={'central': 'mortalityhivneg', 'high': 'mortalityhivneg_ub', 'low': 'mortalityhivneg_lb'})

    # Merge all into one and save the output
    df_resource_need = pandas.concat(
        [incidence_hh_by_year, mortality_hh_by_year, mortalityhivneg_hh_by_year], axis=1)
    df_resource_need.to_csv('df_partner_tb.csv')


