"""
This script produces the analysis that shows the Impact that can achieved for each Global Fund budget scenario, under
Approach A and Approach B.
MEHRAN'S LEFT HAND FIGURE
"""
from collections import defaultdict
from pathlib import Path
from typing import Literal, Dict

import pandas as pd
from matplotlib import pyplot as plt

from scripts.ic7.hiv.hiv_analysis import get_hiv_database

from scripts.ic7.malaria.malaria_analysis import get_malaria_database
from scripts.ic7.tb.tb_analysis import get_tb_database

from tgftools.analysis import Analysis

from tgftools.filehandler import (

    NonTgfFunding,
    Parameters,
    TgfFunding,
)
from scripts.ic7.shared.htm_report import HTMReport
from tgftools.utils import (
    get_data_path,
    get_root_path,
    get_files_with_extension, save_var, load_var,
)

#%%
DO_RUN = False

#%% Run batch of analyses for all the funding scenarios

project_root = get_root_path()
path_to_data_folder = get_data_path()
funding_path = path_to_data_folder / 'IC7' / 'TimEmulationTool' / 'funding'

# Get all the files that have been provided with TGF funding scenarios (using HIV as the tracer)
files_pattern = sorted([
    file.name.removeprefix('hiv_').removesuffix('.csv')
    for file in get_files_with_extension(
        funding_path / 'hiv' / 'tgf', 'csv'
    )
])

# Find the GF funding amounts for HIV, TB, Malaria
scenarios = {
    name: {
        disease: funding_path / disease / 'tgf' / f'{disease}_{name}.csv'
        for disease in ['hiv', 'tb', 'malaria']
    }
    for name in files_pattern
}

# Check that all files are present
for v in scenarios.values():
    for file in v.values():
        assert file.exists(), f"{file} does not exist"

# "Thin-out" the scenarios to make the initial run go faster and to not use any unnecessary scenarios
# - Drop all 'incUnalloc' amounts
scenarios_to_run = {
    k: v for k, v in scenarios.items()
    if not k.endswith('_incUnalloc')
}

# - Don't run every scenario
thinning_factor = 3  # 1 implies no thinning
scenarios_to_run = {
    k: v for i, (k, v) in enumerate(scenarios_to_run.items()) if i % thinning_factor == 0
}


# Load the databases for HIV, Tb and Malaria
# Declare the parameters, indicators and scenarios
parameters = Parameters(project_root / "src" / "scripts" / "ic7" / "shared" / "parameters.toml")

hiv_db = get_hiv_database(load_data_from_raw_files=False)
tb_db = get_tb_database(load_data_from_raw_files=False)
malaria_db = get_malaria_database(load_data_from_raw_files=False)

# Declare assumptions that are not going to change in the analysis
NON_TGF_FUNDING = '_nonFubgible_dipiBase.csv'
SCENARIO_DESCRIPTOR = 'IC_IC'


def get_projections(
        approach: Literal['a', 'b'] = 'a',
        tgf_funding_scenario: str = '',
        innovation_on: bool = False,
        gp: bool = False
) -> Dict:
    """Returns Dict of portfolio results, keyed by disease. As this must work for GP and model results, we only return
    the portfolio results (GP is not defined at the country level here)."""

    # Create Analysis objects for this funding scenario
    analysis_hiv = Analysis(
        database=hiv_db,
        scenario_descriptor=SCENARIO_DESCRIPTOR,
        tgf_funding=TgfFunding(scenarios[tgf_funding_scenario]['hiv']),
        non_tgf_funding=NonTgfFunding(funding_path / 'hiv' / 'non_tgf' / f'hiv{NON_TGF_FUNDING}'),
        parameters=parameters,
        handle_out_of_bounds_costs=True,
        innovation_on=innovation_on,
    )
    analysis_tb = Analysis(
        database=tb_db,
        scenario_descriptor=SCENARIO_DESCRIPTOR,
        tgf_funding=TgfFunding(scenarios[tgf_funding_scenario]['tb']),
        non_tgf_funding=NonTgfFunding(funding_path / 'tb' / 'non_tgf' / f'tb{NON_TGF_FUNDING}'),
        parameters=parameters,
        handle_out_of_bounds_costs=True,
        innovation_on=innovation_on,
    )
    analysis_malaria = Analysis(
        database=tb_db,
        scenario_descriptor=SCENARIO_DESCRIPTOR,
        tgf_funding=TgfFunding(scenarios[tgf_funding_scenario]['malaria']),
        non_tgf_funding=NonTgfFunding(funding_path / 'malaria' / 'non_tgf' / f'malaria{NON_TGF_FUNDING}'),
        parameters=parameters,
        handle_out_of_bounds_costs=True,
        innovation_on=innovation_on,
    )

    if not gp:
        if approach == 'a':
            return dict(
                hiv=analysis_hiv.portfolio_projection_approach_a().portfolio_results,
                tb=analysis_tb.portfolio_projection_approach_a().portfolio_results,
                malaria=analysis_malaria.portfolio_projection_approach_a().portfolio_results,
            )
        elif approach == 'b':
            optimisation_params = {
                'years_for_obj_func': parameters.get('YEARS_FOR_OBJ_FUNC'),
                'force_monotonic_decreasing': True
            }
            return dict(
                hiv=analysis_hiv.portfolio_projection_approach_b(methods=['ga_backwards'], optimisation_params=optimisation_params).portfolio_results,
                tb=analysis_tb.portfolio_projection_approach_b(methods=['ga_backwards'], optimisation_params=optimisation_params).portfolio_results,
                malaria=analysis_malaria.portfolio_projection_approach_a().portfolio_results,
                # todo: Couldn't get Approach B to work, as some countries that should be modelled were not in the
                #  results (e.g. COM), so using ApproachA as placeholder
            )
    else:
        # Return the GP
        def convert_format(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
            """Convert the GP into the same format as `PortfolioProjection.portfolio_results` (i.e. dict and dfs, keyed
            by indicator), with columns for model_central/low/high."""
            return {
                c: pd.DataFrame({col_name: df[c] for col_name in ('model_central', 'model_low', 'model_high')})
                for c in df.columns
            }

        return dict(
            hiv=convert_format(analysis_hiv.get_gp()),
            tb=convert_format(analysis_tb.get_gp()),
            malaria=convert_format(analysis_malaria.get_gp()),
        )


#%% For each scenario, do the analysis under Approach A and Approach B and compile the results
if DO_RUN:
    Results = dict()
    for scenario_label in scenarios_to_run:
        Results[scenario_label] = get_projections(approach='a', innovation_on=False, tgf_funding_scenario=scenario_label)

    # Now produce the variations on this that are required.
    Results['$11Bn: With Innovation'] = get_projections(approach='a', innovation_on=True, tgf_funding_scenario='Fubgible_gf_11b')

    Results['$11Bn: Incl. Unalloc'] = get_projections(approach='a', innovation_on=False, tgf_funding_scenario='Fubgible_gf_11b_incUnalloc')

    Results['$11Bn: Approach B'] = get_projections(approach='b', innovation_on=False, tgf_funding_scenario='Fubgible_gf_11b')

    Results['$11Bn: Approach B & Incl. Unalloc'] = get_projections(approach='b', innovation_on=False, tgf_funding_scenario='Fubgible_gf_11b_incUnalloc')

    Results['$11Bn: Approach B & With Innovation'] = get_projections(approach='b', innovation_on=True, tgf_funding_scenario='Fubgible_gf_11b')

    Results['$11Bn: Approach B & Incl. Unalloc & With Innovation'] = get_projections(approach='b', innovation_on=True, tgf_funding_scenario='Fubgible_gf_11b_incUnalloc')

    Results['GP'] = get_projections(gp=True, approach='a', innovation_on=False, tgf_funding_scenario='Fubgible_gf_11b')

    save_var(Results, get_root_path() / "sessions" / "Results.pkl")
else:
    Results = load_var(get_root_path() / "sessions" / "Results.pkl")


#%% Construct statistics

def get_percent_reduction_from_2024_to_2030(r, indicator: str) -> pd.DataFrame:
    """Find the percentage reduction in the indicator from 2024 to 2030.
    :param: `indicator` might be 'cases' or 'deaths' or another indicator."""
    s = defaultdict(dict)
    for disease in ('hiv', 'tb', 'malaria'):
        for scenario in r:
            s[disease][scenario] = 100 * (
                    1.0 - r[scenario][disease][indicator].at[2030, 'model_central'] / r[scenario][disease][indicator].at[2024, 'model_central']
            )
    return pd.DataFrame(s)

def get_sum_of_indicator_during_2024_to_2030_as_percent_of_gp(r, indicator: str) -> pd.DataFrame:
    """Find the value of the indicator, summed in the period 2024-2030, relative to the value in GP.
    :param: `indicator` might be 'cases' or 'deaths' or another indicator."""
    s = defaultdict(dict)
    for disease in ('hiv', 'tb', 'malaria'):
        gp_total = r['GP'][disease][indicator].loc[slice(2024, 2030)]['model_central'].sum()
        for scenario in r:
            scenario_total = r[scenario][disease][indicator].loc[slice(2024, 2030)]['model_central'].sum()
            s[disease][scenario] = 100 * (scenario_total / gp_total)
    return pd.DataFrame(s)

def get_percent_reduction_in_indicator_from_2030_vs_2024_relative_to_gp(r, indicator: str) -> pd.DataFrame:
    """Find the percentage of the reduction that is achieved in each result, relative to GP.
    e.g., if GP reduces cases by 80% from 2024 to 2030, and the scenario reduces cases by 40%: the result is 50%
    :param: `indicator` might be 'cases' or 'deaths' or another indicator.
    """
    s = defaultdict(dict)
    for disease in ('hiv', 'tb', 'malaria'):
        gp_reduction = 1.0 - (r['GP'][disease][indicator].at[2030, 'model_central'] / r['GP'][disease][indicator].at[2024,'model_central'])
        for scenario in r:
            scenario_reduction = 1.0 - (r[scenario][disease][indicator].at[2030, 'model_central'] / r[scenario][disease][indicator].at[2024, 'model_central'])
            s[disease][scenario] = 100 * scenario_reduction / gp_reduction
    return pd.DataFrame(s)


stats = {
    'cases percent reduction 2024 to 2040': get_percent_reduction_from_2024_to_2030(Results, indicator='cases'),
    'deaths percent reduction 2024 to 2040': get_percent_reduction_from_2024_to_2030(Results, indicator='deaths'),
    'cases_relative_to_gp': get_sum_of_indicator_during_2024_to_2030_as_percent_of_gp(Results, indicator='cases'),
    'deaths_relative_to_gp': get_sum_of_indicator_during_2024_to_2030_as_percent_of_gp(Results, indicator='deaths'),
    'cases_reduction_vs_gp': get_percent_reduction_in_indicator_from_2030_vs_2024_relative_to_gp(Results, indicator='cases'),
    'deaths_reduction_vs_gp': get_percent_reduction_in_indicator_from_2030_vs_2024_relative_to_gp(Results, indicator='deaths'),
}

# Add the combination one: across cases and deaths and all disease
stats['cases_and_deaths_reduction_vs_gp'] = (stats['cases_reduction_vs_gp'] + stats['deaths_reduction_vs_gp']) / 2
stats['cases_and_deaths_reduction_vs_gp']['all'] = stats['cases_and_deaths_reduction_vs_gp'].mean(axis=1)



#%% Functions for making nice figures

mapper_to_pretty_names = {
    n: f"${n.removeprefix('Fubgible_gf_').replace('b', 'Bn').replace('_incUnalloc', '+')}"
    for n in sorted(list(scenarios.keys()))
}

# Get the sum of the funding (across countries and diseases) for each of the scenarios
def get_total_funding(p: Path) -> float:
    return pd.read_csv(p)['cost'].sum()

tot_tgf_funding = pd.Series({
    mapper_to_pretty_names[scenario_name]: sum(list(map(get_total_funding, files.values())))
    for scenario_name, files in scenarios.items()
}).sort_index()
tot_tgf_funding.name = 'TGF Funding'

def make_graph(df: pd.Series, title: str):
    # plot the black dots: approach A across all budget levels
    black_dots = pd.DataFrame(df.copy())
    black_dots.index = black_dots.index.map(mapper_to_pretty_names)
    black_dots = black_dots.loc[black_dots.index.notna()]
    black_dots['x_pos'] = black_dots.index.map(tot_tgf_funding.to_dict())

    fig, ax = plt.subplots()
    ax.plot(
        black_dots['x_pos'],
        black_dots[black_dots.columns[0]],
        color='black',
        marker='.',
        markersize=10,
        linestyle='none',
        label='Approach A',
    )
    ax.plot(
        black_dots.at['$11Bn', 'x_pos'],
        df['$11Bn: With Innovation'],
        color='red',
        marker='.',
        markersize=10,
        linestyle='none',
        label='With Innovation'
    )
    ax.plot(
        black_dots.at['$11Bn', 'x_pos'],
        df['$11Bn: Approach B'],
        color='green',
        marker='.',
        markersize=10,
        linestyle='none',
        label='Approach B'
    )
    ax.plot(
        black_dots.at['$11Bn', 'x_pos'],
        df['$11Bn: Incl. Unalloc'],
        color='orange',
        marker='.',
        markersize=10,
        linestyle='none',
        label='Including Unallocated Amounts'
    )
    ax.plot(
        black_dots.at['$11Bn', 'x_pos'],
        df['$11Bn: Approach B & Incl. Unalloc'],
        color='purple',
        marker='.',
        markersize=10,
        linestyle='none',
        label='Approach B, Including Unallocated Amounts'
    )
    ax.plot(
        black_dots.at['$11Bn', 'x_pos'],
        df['$11Bn: Approach B & With Innovation'],
        color='yellow',
        marker='.',
        markersize=10,
        linestyle='none',
        label='Approach B, With Innovation'
    )
    ax.plot(
        black_dots.at['$11Bn', 'x_pos'],
        df['$11Bn: Approach B & Incl. Unalloc & With Innovation'],
        color='magenta',
        marker='.',
        markersize=10,
        linestyle='none',
        label='Approach B,  Including Unallocated Amounts & With Innovation'
    )
    ax.set_ylabel('%')
    ax.set_xlabel('TGF Replenishment Scenario')
    ax.set_xticks(black_dots.x_pos)
    ax.set_xticklabels(black_dots.index)
    ax.set_title(title)
    ax.legend()
    fig.savefig(project_root / 'outputs' / f"{title}.png")
    fig.tight_layout()
    fig.show()
    plt.close(fig)


#%% Make graphs:
make_graph(
    stats['cases_and_deaths_reduction_vs_gp']['all'],
    title='Percent of GP Reduction in Cases and Deaths: All Diseases',
)

for stat in stats:
    for disease in ('hiv', 'tb', 'malaria'):
        make_graph(
            stats[stat][disease],
            title=f'{stat}: {disease}',
        )





# todo right-hand side figure
# ---------------------------
# require running at wide range of TGF scenario, provided a total amount only. and under approach B