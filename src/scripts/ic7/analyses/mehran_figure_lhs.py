"""
This script produces the analysis that shows the Impact that can achieved for each Global Fund budget scenario, under
Approach A and Approach B.
MEHRAN'S LEFT HAND FIGURE
"""
from pathlib import Path
from typing import Literal

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

# "Thin-out" the scenarios to make the initial run go faster and to not use any unneccessary scenarios
# Drop all 'incUnalloc' amounts
scenarios_to_run = {
    k: v for k, v in scenarios.items()
    if not k.endswith('_incUnalloc')
}

thinning_factor = 3  # 1 implies no thining
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
):

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
        # Produce a report for this funding scenario under Approach A
        if approach == 'a':
            return HTMReport(
                hiv=analysis_hiv.portfolio_projection_approach_a(),
                tb=analysis_tb.portfolio_projection_approach_a(),
                malaria=analysis_malaria.portfolio_projection_approach_a(),
            )
        elif approach == 'b':
            # Produce a report for this funding scenario under Approach B (greedy-algorithm-backwards)
            optimisation_params = {
                'years_for_obj_func': parameters.get('YEARS_FOR_OBJ_FUNC'),
                'force_monotonic_decreasing': True
            }
            return HTMReport(
                hiv=analysis_hiv.portfolio_projection_approach_b(
                    methods=['ga_backwards'], optimisation_params=optimisation_params),
                tb=analysis_tb.portfolio_projection_approach_b(
                    methods=['ga_backwards'], optimisation_params=optimisation_params),
                malaria=analysis_malaria.portfolio_projection_approach_a(),
                # todo: Couldn't get Approach B to work, as some countries that should be modelled were not in the results (e.g. COM), so using ApproachA as placeholder
                # malaria=analysis_malaria.portfolio_projection_approach_b(
                #   methods=['ga_backwards'], optimisation_params=optimisation_params),
            )
    else:
        return dict(
            hiv=analysis_hiv.get_gp(),
            tb=analysis_tb.get_gp(),
            malaria=analysis_malaria.get_gp(),
        )


# For each scenario, do the analysis under Approach A and Approach B and compile the results
if DO_RUN:
    Results = dict()
    for scenario_label in scenarios_to_run:
        Results[scenario_label] = get_projections(approach='a', innovation_on=False, tgf_funding_scenario=scenario_label)

    # Now produce the variations on this that are required.
    Results['$11Bn: With Innovation'] = get_projections(approach='a', innovation_on=True, tgf_funding_scenario='Fubgible_gf_11b')

    Results['$11Bn: Approach B'] = get_projections(approach='b', innovation_on=True, tgf_funding_scenario='Fubgible_gf_11b')

    Results['$11Bn: Inc. Unalloc'] = get_projections(approach='a', innovation_on=True, tgf_funding_scenario='Fubgible_gf_11b_incUnalloc')

    save_var(Results, get_root_path() / "sessions" / "Results.pkl")
else:
    Results = load_var(get_root_path() / "sessions" / "Results.pkl")

def get_cases_and_deaths(r) -> dict(dict()):
    """returns the cases and deaths for this projection, in the form: {<disease>: {'cases': X, 'deaths': Y}}"""

    TARGET_YEARS = slice(2024, 2030)

    return {
        'hiv': {
            'cases': r.hiv.portfolio_results['cases'].loc[TARGET_YEARS]['model_central'].sum(),
            'deaths': r.hiv.portfolio_results['deaths'].loc[TARGET_YEARS]['model_central'].sum(),
        },
        'tb': {
            'cases': r.tb.portfolio_results['cases'].loc[TARGET_YEARS]['model_central'].sum(),
            'deaths': r.tb.portfolio_results['deaths'].loc[TARGET_YEARS]['model_central'].sum(),
        },
        'malaria': {
            'cases': r.malaria.portfolio_results['cases'].loc[TARGET_YEARS]['model_central'].sum(),
            'deaths': r.malaria.portfolio_results['deaths'].loc[TARGET_YEARS]['model_central'].sum(),
        }
    }

stats = pd.DataFrame({
    k: get_cases_and_deaths(v)
    for k, v in Results.items()
})

# Get results
# for GP:
gp_proj = get_projections(gp=True, approach='a', innovation_on=False, tgf_funding_scenario='Fubgible_gf_11b')
TARGET_YEARS = slice(2024, 2030)
gp_stats = {
        'hiv': {
            'cases': gp_proj['hiv']['cases'].loc[TARGET_YEARS].sum(),
            'deaths': gp_proj['hiv']['deaths'].loc[TARGET_YEARS].sum(),
        },
        'tb': {
            'cases': gp_proj['tb']['cases'].loc[TARGET_YEARS].sum(),
            'deaths': gp_proj['tb']['deaths'].loc[TARGET_YEARS].sum(),
        },
        'malaria': {
            'cases': gp_proj['malaria']['cases'].loc[TARGET_YEARS].sum(),
            'deaths': gp_proj['malaria']['deaths'].loc[TARGET_YEARS].sum(),
        }
    }

# % of GP reduction in cases and deaths, for each disease
pc_reduc_hiv = 100 * (1 / stats.loc['hiv'].apply(pd.Series).div(pd.Series(gp_stats['hiv'])))
pc_reduc_tb = 100 * (1. / stats.loc['tb'].apply(pd.Series).div(pd.Series(gp_stats['tb'])))
pc_reduc_malaria = 100 * (1. / stats.loc['malaria'].apply(pd.Series).div(pd.Series(gp_stats['malaria'])))

# % of GP reduction in cases and deaths (averaged), acrosss all diseases (averaged)
pc_reduc_all = (
        pc_reduc_hiv.mean(axis=1) + pc_reduc_tb.mean(axis=1) + pc_reduc_malaria.mean(axis=1)
)/3


#%% Make nice figures

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

tgf_funding_by_disease = pd.DataFrame({
    mapper_to_pretty_names[scenario_name]: {
        disease: get_total_funding(filename)
        for disease, filename in files.items()
    }
    for scenario_name, files in scenarios.items()
}).T.sort_index()
tgf_funding_by_disease['total'] = tgf_funding_by_disease.sum(axis=1)




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
        df['$11Bn: Inc. Unalloc'],
        color='orange',
        marker='.',
        markersize=10,
        linestyle='none',
        label='Including Unallocated Amounts'
    )
    ax.set_ylabel('% of GP reduction achieved')
    ax.set_xlabel('TGF Replenishment Scenario')
    ax.set_ylim(0, 100)
    # todo label xtickabels
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.show()


make_graph(pc_reduc_all, title='All Diseases, Across Cases and Deaths')
make_graph(pc_reduc_hiv['cases'], title='HIV Cases')
make_graph(pc_reduc_hiv['deaths'], title='HIV Deaths')
make_graph(pc_reduc_tb['cases'], title='TB Cases')
make_graph(pc_reduc_tb['deaths'], title='TB Deaths')
make_graph(pc_reduc_malaria['cases'], title='Malaria Cases')
make_graph(pc_reduc_malaria['deaths'], title='Malaria Deaths')


# todo pdf saving
# ---------------------------


# todo right-hand side figure
# ---------------------------
# require running at wide range of TGF scenario, provided a total amount only. and under approach B