"""The file is for the analysis where we allow allocation of fundings across the diseases and the countries, in order
to find whether the GF allocation resembles the optimal allocation (for a given definition of 'optimal')."""
from pathlib import Path

import pandas as pd
from matplotlib import pyplot as plt

from scripts.ic7.hiv.hiv_analysis import get_hiv_database
from scripts.ic7.malaria.malaria_analysis import get_malaria_database
from scripts.ic7.tb.tb_analysis import get_tb_database
from tgftools.analysis import Analysis
from tgftools.approach_b import ApproachB, add_list_of_results
from tgftools.filehandler import (
    NonTgfFunding,
    Parameters,
    TgfFunding,
)
from tgftools.utils import (
    get_data_path,
    get_root_path,
    open_file, save_var, load_var,
)

DO_RUN = False

#%% Load the data for HIV, Tb and Malaria

# Declare path
project_root = get_root_path()
path_to_data_folder = get_data_path()
funding_path = path_to_data_folder / 'IC7' / 'TimEmulationTool' / 'funding'
outputs_path = get_root_path() / 'outputs'

# Declare the parameters, indicators and scenarios
parameters = Parameters(project_root / "src" / "scripts" / "ic7" / "shared" / "parameters.toml")

# Load databases
db = {
    'hiv': get_hiv_database(load_data_from_raw_files=False),
    'tb': get_tb_database(load_data_from_raw_files=False),
    'malaria': get_malaria_database(load_data_from_raw_files=False),
}

# Declare assumptions that are not going to change in the analysis
NON_TGF_FUNDING = '_nonFubgible_dipiBase.csv'
SCENARIO_DESCRIPTOR = 'IC_IC'

# Create TGF Funding Scenarios from the bespoke files
def get_tgf_funding_scenario(disease: str) -> TgfFunding:
    """Find to load and reformat the new scenario file.
    N.B.Previously, we've used the file thus: TgfFunding(funding_path / disease / 'tgf' / f'{disease}_{TGF_FUNDING}.csv')
    """
    local_path_for_files = Path(
        '/Users/tbh03/Library/CloudStorage/OneDrive-ImperialCollegeLondon/Documents/Global Fund/2024/Cross-Disease Allocation/2024_08_20')
    if disease == 'hiv':
        file = local_path_for_files / '$13.128b_HIVAIDS.csv'
    elif disease == 'tb':
        file = local_path_for_files / '$11b_Tuberculosis.csv'
    elif disease == 'malaria':
        file = local_path_for_files / '$13.128b_Malaria.csv'
    else:
        raise ValueError

    df = pd.read_csv(file).rename(columns={'ISO3': 'country', 'AmountUSD': 'value'}).set_index('country')[['value']]

    # Get original file that this should be based on:
    orig = TgfFunding(funding_path / disease / 'tgf' / f'{disease}_Fubgible_gf_17b.csv').df

    # Cut-out countries from the new file that were not present in old file (Should check this assumption)
    df = df.loc[df.index.isin(orig.index)]
    # Add zero-line for any country that is not in the new file but was in the old file
    for _c in list(set(orig.index) - set(df.index)):
        df.loc[_c, 'value'] = 0
    pd.testing.assert_index_equal(orig.index, df.index, check_order=False)

    return TgfFunding.from_df(df.astype({'value': 'int'}))


#%% Gerrymander the analysis.

# Approach:
# We will create an imaginary new disease (which is, in effect, the disease of HIV-or-TB-or-Malaria) and we will compete
# the production functions that are available to combat this disease in the entire portfolio. For example, deaths are
# averted from this new disease by investing in HIV programs in country X, Tb programs in country Y, malaria programs
# in country Z, or in any disease/country program. In essence, each country-disease production function is competing
# with all others. We will then see where the funding is directed to, w.r.t. disease.

# Note that objective function for this analysis is balance of reducing cases and deaths, but we know that cases of
# malaria are more numerous than cases of TB or infections of HIV, and this will skew results towards malaria.
# So, we have to edit the objective function in ApproachB so that it responds only to deaths.

# Practically, we will create an Analysis class for each disease and get the data-frames that would go into an
# ApproachB optimisation analysis. We will then put them into one dataset all together, renaming the country to
# signal which disease is implicitly being funded when using that production function.

optimisation_params = {
    'years_for_obj_func': parameters.get('YEARS_FOR_OBJ_FUNC'),
    'force_monotonic_decreasing': True
}
approach_b_datasets = {
    disease: Analysis(
        database=db[disease],
        scenario_descriptor=SCENARIO_DESCRIPTOR,
        tgf_funding=get_tgf_funding_scenario(disease),
        non_tgf_funding=NonTgfFunding(funding_path / disease / 'non_tgf' / f'{disease}{NON_TGF_FUNDING}'),
        parameters=parameters,
        handle_out_of_bounds_costs=True,
        innovation_on=True,
    ).get_data_frames_for_approach_b(optimisation_params=optimisation_params)
    for disease in ['hiv', 'tb', 'malaria']
}

def add_prexix_to_country(df: pd.DataFrame, prefix: str) -> pd.DataFrame:
    df['country'] = prefix + df['country']
    return df

# Combine these dataset into one, before passing into ApproachB
tgf_budgets = pd.concat([
    add_prexix_to_country(approach_b_datasets[disease]['tgf_budgets'], disease)
    for disease in ['hiv', 'tb', 'malaria']
    ], axis=0)

non_tgf_budgets = pd.concat([
    add_prexix_to_country(approach_b_datasets[disease]['non_tgf_budgets'], disease)
    for disease in ['hiv', 'tb', 'malaria']
    ], axis=0)

model_results = pd.concat([
    add_prexix_to_country(approach_b_datasets[disease]['model_results'], disease)
    for disease in ['hiv', 'tb', 'malaria']
    ], axis=0)

# Make an ApproachB object that uses these synthetic datasets and get results from Approach A and Approach B
# - Override the objective function to be bespoke to this analysis, and only responding to reduce the number of deaths

class ApproachB_WithOptimisationForReducingDeathsOnly(ApproachB):
    def eval_objective_function(self, results: list['ResultDatum']) -> float:
        """Return total of deaths across all the results (for all countries and diseases).
        (This is over-writing the usual objective function that is based on reducing cases and deaths.)"""
        return add_list_of_results(results).deaths

approach_b = ApproachB_WithOptimisationForReducingDeathsOnly(
    model_results=model_results,
    non_tgf_budgets=non_tgf_budgets,
    tgf_budgets=tgf_budgets,
)
# If needed, could produce plots of these functions using:
# approach_b.inspect_model_results(
#     filename=outputs_path / 'cross_disease_optimisation_inspect_model_results.pdf',
#     plt_show=False
# )

Scenarios = [
    dict(
        title='Without Constraints',
        max_allocation_to_a_country=1.00,
        max_allocation_within_a_disease_to_a_country=1.00
    ),
    dict(
        title='With Constraints',
        max_allocation_to_a_country=0.075,
        max_allocation_within_a_disease_to_a_country=0.100
    )
]

if DO_RUN:
    Results = dict()
    for s in Scenarios:
        _title = s['title']
        _max_allocation_to_a_country = s['max_allocation_to_a_country']
        _max_allocation_within_a_disease_to_a_country = s['max_allocation_within_a_disease_to_a_country']

        # Run Approach B using the data and capture a report about it
        filename = outputs_path / f'cross_disease_optimisation_{_title}.pdf'
        results = approach_b.run(
            methods=['ga_forwards'],
            provide_best_only=True,
            filename=filename,
            max_allocation_to_a_country=_max_allocation_to_a_country,
            max_allocation_within_a_disease_to_a_country=_max_allocation_within_a_disease_to_a_country
        )
        open_file(filename)
        Results[_title] = results
    save_var(Results, project_root / 'sessions' / 'Results_For_Cross_Disease_Optimisation.pkl')
else:
    Results = load_var(project_root / 'sessions' / 'Results_For_Cross_Disease_Optimisation.pkl')

#%% Inspect the results

for s, results in zip(Scenarios, Results.values()):
    _title = s['title']
    _max_allocation_to_a_country = s['max_allocation_to_a_country']
    _max_allocation_within_a_disease_to_a_country = s['max_allocation_within_a_disease_to_a_country']

    # - Differences in health
    fig, ax = plt.subplots(nrows=1, ncols=2, )
    ax[0].bar(x=['Approach A', 'Approach B'], height=[results['a'].total_result.cases, results['b'].total_result.cases])
    ax[0].set_title(f'{_title}\nCases')
    ax[1].bar(x=['Approach A', 'Approach B'], height=[results['a'].total_result.deaths, results['b'].total_result.deaths])
    ax[1].set_title(f'{_title}\nDeaths')
    fig.tight_layout()
    fig.show()

    # Note that these are not the fully-adjusted portfolio results. To get that, we would need to put these TGF Funding
    # Allocations for each disease into a TGFFunding object, create a new Analysis class using that (as usual, for each
    # country), and then get portfolio results from there (and also summary results from the Report class, if needed).


    # - Difference in Allocation Across the Diseases (i.e. the total that end up being used for each disease, summed across
    #   countries).
    def total_funding_by_disease(d: dict) -> float:
        x = pd.Series(d)
        return x.groupby(x.index.str[0:-3]).sum()  # <--summing by disease, obtained by stripping off last three characters,
        #                                               which are the ISO3 code

    budget_alloc = pd.concat({
        'Approach A': total_funding_by_disease(results['a'].tgf_budget_by_country),
        'Approach B': total_funding_by_disease(results['b'].tgf_budget_by_country),
    }).unstack().T

    fig, ax = plt.subplots()
    budget_alloc.plot.bar(ax=ax)
    ax.set_xlabel("Disease")
    ax.set_ylabel("TGF Funding ($)")
    ax.set_title(f"{_title}\nTGF Funding Allocation To Disease When\nOptimising Across Disease & Country")
    fig.tight_layout()
    fig.show()

    # Get the percentage split
    def plot_table(df):
        fig, ax = plt.subplots()
        ax.axis('off')
        pd.plotting.table(ax, df, loc='center', cellLoc='center', colWidths=list([.2, .2]))
        ax.set_title(_title)
        fig.tight_layout()
        fig.show()

    disease_split = 100 * (budget_alloc['Approach B'] / budget_alloc['Approach B'].sum()).round(3)
    plot_table(disease_split)

    # Show rank-ordered difference between B vs A, to see what is driving the change....
    difference_b_vs_a = (
         pd.Series(results['b'].tgf_budget_by_country) - pd.Series(results['a'].tgf_budget_by_country)
                        ).sort_values()/1e6

    fig, ax = plt.subplots(nrows=1, ncols=2, sharey=True)
    difference_b_vs_a.head(20).plot.bar(ax=ax[0])
    difference_b_vs_a.tail(20).plot.bar(ax=ax[1])
    ax[0].set_ylim([-1200, 1200])
    ax[0].set_ylabel("TGF Funding ($M)\nApproach B - Approach A")
    ax[0].set_title("Top 20 Programs Receiving Less Under B", fontsize=8)
    ax[1].set_title("Top 20 Programs Receiving More Under B", fontsize=8)
    fig.suptitle(_title)
    fig.tight_layout()
    fig.show()

    # Look at amount to each country and each country within disease
    allox_by_country = pd.Series(results['b'].tgf_budget_by_country)
    allox_by_country.index = allox_by_country.index.map(lambda _s: (_s[0:-3], _s[-3:]))

    # - consider the amount that any country can receive
    fr_to_each_country = (allox_by_country.groupby(axis=0, level=1).sum() / allox_by_country.sum()).fillna(0.0)
    fig, ax = plt.subplots()
    (100.* fr_to_each_country).sort_values(ascending=False).head(20).plot.bar(ax=ax)
    ax.set_ylabel('%')
    ax.set_title(f"{_title}\nFraction of All TGF Funding to Each Country")
    ax.axhline(100. * _max_allocation_to_a_country, color='black', linestyle='--')
    ax.set_ylim(top=40)
    fig.tight_layout()
    fig.show()

    # - consider the amount to each country within disease area
    for disease in ('hiv', 'tb', 'malaria'):
        allox_by_country_within_disease = allox_by_country.loc[(disease, slice(None))]
        fig, ax = plt.subplots()
        (100.* allox_by_country_within_disease/allox_by_country_within_disease.sum()).sort_values(ascending=False).head(20).plot.bar(ax=ax)
        ax.set_ylabel('%')
        ax.set_title(f"{_title}\nFraction of TGF Allocation for {disease} to Each Country")
        ax.axhline(100. * _max_allocation_within_a_disease_to_a_country, color='black', linestyle='--')
        ax.set_ylim(top=40)
        fig.tight_layout()
        fig.show()

