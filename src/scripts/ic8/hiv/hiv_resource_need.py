import pandas

from scripts.ic8.hiv.hiv_filehandlers import HIVMixin, PFInputDataHIV, PartnerDataHIV
from scripts.ic8.hiv.hiv_filehandlers import ModelResultsHiv
from tgftools.FilePaths import FilePaths
from tgftools.database import Database
from tgftools.filehandler import Parameters
from tgftools.utils import get_root_path


""" 
This is a simple piece of code that utilizes the Database check class to extract data relating to the PF 100 scenario 
and the GP scenario and partner data . This code is not part of the modular framework. 

When running the resource need make sure to select the desired list of countries in the parameter.toml file. In this 
file, for some diseases, there is a second list which contains all modelled countries. This gives the option to extract
data for all modelled countries or those used in the IC. 
"""


class DatabaseChecksHiv(HIVMixin,):
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

    cases_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'cases')
    ]
    deaths_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'deaths')
    ]
    plhiv_df = model_results.df.loc[
        ("PF", 1, slice(None), slice(None), 'population')
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
        [cost_by_year, incidence_by_year, mortality_by_year, cases_by_year, deaths_by_year, plhiv_by_year, hivneg_by_year], axis=1)
    df_resource_need.to_csv('df_pf_100_hiv.csv')

    # Run data from GP scenario:
    cases_df = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'cases')
    ]
    deaths_df = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'deaths')
    ]
    plhiv_df = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'population')
    ]
    hivneg_df = model_results.df.loc[
        ("GP", 1, slice(None), slice(None), 'hivneg')
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
        [incidence_by_year, mortality_by_year], axis=1)
    df_resource_need.to_csv('df_gp_hiv.csv')

    # Get data from partner data
    elig_countries = parameters.get_portfolio_countries_for('HIV')
    cases_df_hh = partner_data.df.loc[
        (slice(None), elig_countries, slice(None), 'cases')
    ]
    deaths_df_hh = partner_data.df.loc[
        (slice(None), elig_countries, slice(None), 'deaths')
    ]
    plhiv_df_hh = partner_data.df.loc[
        (slice(None), elig_countries, slice(None), 'population')
    ]
    hivneg_df_hh = partner_data.df.loc[
        (slice(None), elig_countries, slice(None), 'hivneg')
    ]

    cases_df_hh = cases_df_hh.reset_index()
    cases_by_year_hh = cases_df_hh.groupby(['year'], as_index=True).sum()
    columns_to_drop = ['country', 'scenario_descriptor', 'indicator']
    cases_by_year_hh = cases_by_year_hh.drop(columns=columns_to_drop, axis=1)

    deaths_df_hh = deaths_df_hh.reset_index()
    deaths_by_year_hh = deaths_df_hh.groupby(['year'], as_index=True).sum()
    deaths_by_year_hh = deaths_by_year_hh.drop(columns=columns_to_drop, axis=1)

    plhiv_df_hh = plhiv_df_hh.reset_index()
    plhiv_by_year_hh = plhiv_df_hh.groupby(['year'], as_index=True).sum()
    plhiv_by_year_hh = plhiv_by_year_hh.drop(columns=columns_to_drop, axis=1)

    hivneg_df_hh = hivneg_df_hh.reset_index()
    hivneg_by_year_hh = hivneg_df_hh.groupby(['year'], as_index=True).sum()
    hivneg_by_year_hh = hivneg_by_year_hh.drop(columns=columns_to_drop, axis=1)

    incidence_by_year_hh = cases_by_year_hh / hivneg_by_year_hh
    mortality_by_year_hh = deaths_by_year_hh / plhiv_by_year_hh

    incidence_by_year_hh = incidence_by_year_hh.rename(
        columns={'central': 'incidence', })
    mortality_by_year_hh = mortality_by_year_hh.rename(
        columns={'central': 'mortality', })

    # Merge all into one and save the output
    df_resource_need = pandas.concat(
        [incidence_by_year_hh, mortality_by_year_hh], axis=1)
    df_resource_need.to_csv('df_partner_hiv.csv')
