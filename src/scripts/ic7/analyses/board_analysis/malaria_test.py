import matplotlib
import pandas as pd
from matplotlib import pyplot as plt, ticker
from matplotlib.ticker import FormatStrFormatter, StrMethodFormatter

from scripts.ic7.malaria.malaria_checks import DatabaseChecksMalaria
from scripts.ic7.malaria.malaria_filehandlers import PFInputDataMalaria, PartnerDataMalaria, GpMalaria, ModelResultsMalaria
from tgftools import analysis
from tgftools.analysis import Analysis
from tgftools.approach_b import explore_approach_b
from tgftools.database import Database
from tgftools.filehandler import (
    FixedGp,
    NonTgfFunding,
    Parameters,
    TgfFunding,
)
from tgftools.utils import (
    get_data_path,
    get_root_path,
    load_var,
    save_var,
)

""" This script runs a number of GF amounts with proportional decreases in the dipiBase file, which contains information 
on both domestic and allocated non GF external funding. The idea is to these scenarios and understand the lationship 
between the new funding envelope and total GP need to map if this corresponds to the proportional reduction in impact
as defined by cases and deaths. """

# Define the scenarios to be run using the files to be selected for each
scenarios = {
    "scenario1": {
        "gf_amount": "malaria_Fubgible_gf_11b_incUnalloc.csv",
        "non_gf_amount": "malaria_nonFubgible_dipiBase_11bn_domesticonly.csv",
    },
    "scenario2": {
        "gf_amount": "malaria_Fubgible_gf_11b_incUnalloc.csv",
        "non_gf_amount": "malaria_nonFubgible_dipiBase.csv",
    },
    "scenario3": {
        "gf_amount": "malaria_Fubgible_gf_16b_incUnalloc.csv",
        "non_gf_amount": "malaria_nonFubgible_dipiBase_16bn_domesticonly.csv",
    },
    "scenario4": {
        "gf_amount": "malaria_Fubgible_gf_16b_incUnalloc.csv",
        "non_gf_amount": "malaria_nonFubgible_dipiBase.csv",
    },
    "scenario5": {
        "gf_amount": "malaria_Fubgible_gf_17b_incUnalloc.csv",
        "non_gf_amount": "malaria_nonFubgible_dipiBase.csv",
    },
}

# Define paths
path_to_data_folder = get_data_path()
project_root = get_root_path()
root_for_file = path_to_data_folder / "IC7/TimEmulationTool" / "funding" / "malaria"

# Declare the parameters, indicators and scenarios
parameters = Parameters(project_root / "src" / "scripts" / "ic7" / "shared" / "parameters.toml")

# Load model results
model_results = ModelResultsMalaria(
    path_to_data_folder / "IC7/TimEmulationTool/modelling_outputs/malaria/standard",
    parameters=parameters,
)

# Load the other files
pf_input_data = PFInputDataMalaria(
    path_to_data_folder / "IC7/TimEmulationTool/pf/malaria",
    parameters=parameters,
)

partner_data = PartnerDataMalaria(
    path_to_data_folder / "IC7/TimEmulationTool/partner/malaria",
    parameters=parameters,
)

fixed_gp = FixedGp(
    get_root_path() / "src" / "scripts" / "IC7" / "shared" / "fixed_gps" / "malaria_gp.csv",
    parameters=parameters,
)

gp = GpMalaria(
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

# Extract GP cost from the model output
gp_malaria_cost = model_results.df.loc[
    ("GP_GP", slice(None), slice(None), slice(2024, 2026), "cost"), 'central'
].groupby(axis=0, level='country').sum()

gp_malaria_cases = model_results.df.loc[
    ("GP_GP", slice(None), slice(None), slice(2024, 2026), "cases"), 'central'
].groupby(axis=0, level='country').sum()

gp_malaria_deaths = model_results.df.loc[
    ("GP_GP", slice(None), slice(None), slice(2024, 2026), "deaths"), 'central'
].groupby(axis=0, level='country').sum()

# Run through scenarios and hold them in dictionary called results
results = dict()

for scenario_name, scenario_file in scenarios.items():
    tgf_funding = TgfFunding(root_for_file / "tgf" / scenario_file["gf_amount"])
    non_tgf_funding = NonTgfFunding(root_for_file / "non_tgf" / scenario_file["non_gf_amount"])

    a = Analysis(
        database=db,
        scenario_descriptor='IC_IC',
        tgf_funding=tgf_funding,
        non_tgf_funding=non_tgf_funding,
        parameters=parameters,
        handle_out_of_bounds_costs=True,
        innovation_on=True,
    )

    ApproachB = a.portfolio_projection_approach_b(
        methods=['ga_backwards', 'ga_forwards', ],
        optimisation_params={
            'years_for_obj_func': parameters.get('YEARS_FOR_OBJ_FUNC'),
            'force_monotonic_decreasing': True,
        },
    )

    results[scenario_name] = ApproachB

# Collect funding info to check against csv files
tgf_funding_check = dict()
non_tgf_funding_check = dict()

for x in scenarios.keys():
    tgf_funding_check[x] = results[x].tgf_funding_by_country
    non_tgf_funding_check[x] = results[x].non_tgf_funding_by_country

tgf_funding_check = pd.DataFrame(tgf_funding_check)
non_tgf_funding_check = pd.DataFrame(non_tgf_funding_check)

sum_funding = tgf_funding_check + non_tgf_funding_check

# Collect deaths
deaths_check = dict()

for x in scenarios.keys():
    country_results = results[x].country_results
    deaths_by_country = dict()
    for country_name, country_result in country_results.items():
        deaths_by_country[country_name] = country_result.model_projection_adj['deaths'].loc[
            slice(2024, 2026), "model_central"].sum()
    deaths_check[x] = deaths_by_country

deaths_check = pd.DataFrame(deaths_check)

# Collect cases
cases_check = dict()

for x in scenarios.keys():
    country_results = results[x].country_results
    cases_by_country = dict()
    for country_name, country_result in country_results.items():
        cases_by_country[country_name] = country_result.model_projection_adj['cases'].loc[
            slice(2024, 2026), "model_central"].sum()
    cases_check[x] = cases_by_country

cases_check = pd.DataFrame(cases_check)

# Collect funding as fraction of GP
gp_funding_fraction = sum_funding.apply(lambda s: s / gp_malaria_cost)

# Get portfolio fractions of GP
sum_funding_total = sum_funding.sum()
cases_portfolio = cases_check.sum()
deaths_portfolio = deaths_check.sum()
portfolio_df = pd.concat([sum_funding_total, cases_portfolio, deaths_portfolio], keys = ['cost', 'cases', 'deaths'], axis=1)

gp_portfolio_cost = gp_malaria_cost.sum()
gp_portfolio_cases = gp_malaria_cases.sum()
gp_portfolio_deaths = gp_malaria_deaths.sum()
gp_portfolio_df = pd.DataFrame({'cost': gp_portfolio_cost,
                   'cases': gp_portfolio_cases,
                   'deaths': gp_portfolio_deaths},
                  ['gp'])
portfolio_df = portfolio_df._append(gp_portfolio_df)
data_graph = portfolio_df / portfolio_df.iloc[-1]


cost_impact = pd.DataFrame()
# Plot each of the country cost: impact curves
for c in model_results.countries:
    cases = model_results.df.loc[
        ("IC_IC", slice(None), c, slice(2024, 2026), 'cases'), 'central'
    ].groupby(axis=0, level='funding_fraction').sum()
    deaths = model_results.df.loc[
        ("IC_IC", slice(None), c, slice(2024, 2026), 'deaths'), 'central'
    ].groupby(axis=0, level='funding_fraction').sum()

    temp = pd.DataFrame(
        {
            'country': c,
            'cases': cases,
            "deaths": deaths
        }
    )
    cost_impact = pd.concat([cost_impact, temp])

    # plot each country
    temp.plot()
    plt.title(c)
    plt.show()

# Check single country and plot

iso = "RWA"

ISO_cost = model_results.df.loc[
               ("IC_IC", slice(None), iso , slice(2024, 2026), 'cost'), 'central'
           ].groupby(axis=0, level='funding_fraction').sum() / gp_malaria_cost[iso]

ISO_deaths = model_results.df.loc[
    ("IC_IC", slice(None), iso, slice(2024, 2026), 'deaths'), 'central'
].groupby(axis=0, level='funding_fraction').sum()

ISO_cases = model_results.df.loc[
    ("IC_IC", slice(None), iso, slice(2024, 2026), 'cases'), 'central'
].groupby(axis=0, level='funding_fraction').sum()
ISO_review = pd.concat({'deaths': ISO_deaths, 'cases': ISO_cases}, axis=1)

ISO_review.plot()
plt.show()
plt.title(iso)

fig, ax1 = plt.subplots()

color = 'tab:red'
ax1.set_xlabel('funding fraction')
ax1.set_ylabel('deaths', color=color)
ax1.plot(ISO_deaths, color=color)
ax1.tick_params(axis='y', labelcolor=color)
ax1.title.set_text(iso)

ax2 = ax1.twinx()  # instantiate a second Axes that shares the same x-axis

color = 'tab:blue'
ax2.set_ylabel('cases', color=color)  # we already handled the x-label with ax1
ax2.plot(ISO_cases, color=color)
ax2.tick_params(axis='y', labelcolor=color)

fig.tight_layout()  # otherwise the right y-label is slightly clipped
plt.show()
