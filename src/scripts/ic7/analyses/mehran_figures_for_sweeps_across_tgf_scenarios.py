"""
This script produces the analysis that shows the Impact that can achieved for each Global Fund budget scenario, under
Approach A and Approach B.
This generates the graphs referred to as Mehran's figure left and right-hand versions (Issue #30).
"""

from collections import defaultdict
from typing import Literal, Dict

import numpy as np
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
from tgftools.utils import (
    get_data_path,
    get_root_path,
    get_files_with_extension, save_var, load_var,
)

# Declare paths
project_root = get_root_path()
path_to_data_folder = get_data_path()

# %% Flag to indicate whether the script should reload model results from raw files and re-run all the analysis, or
# instead to re-load locally-cached versions of `ModelResults` binaries and locally-cached version of the analysis
# results.
DO_RUN = False

# %% Find scenarios defined for GF Funding
funding_path = path_to_data_folder / 'IC7' / 'TimEmulationTool' / 'funding'

# Get all the files that have been provided with TGF funding scenarios (using HIV as the tracer)
files_pattern = sorted([
    file.name.removeprefix('hiv_').removesuffix('.csv')
    for file in get_files_with_extension(
        funding_path / 'hiv' / 'tgf', 'csv'
    )
])

# Find the GF funding scenarios for HIV, TB, Malaria
gf_scenarios = {
    name: {
        disease: TgfFunding(funding_path / disease / 'tgf' / f'{disease}_{name}.csv')
        for disease in ['hiv', 'tb', 'malaria']
    }
    for name in files_pattern
}

# Create dict that maps these scenario names to "pretty names" (for use when plotting)
mapper_to_pretty_names = {
    n: f"${n.removeprefix('Fubgible_gf_').replace('b', 'Bn').replace('_incUnalloc', '+')}"
    for n in sorted(list(gf_scenarios.keys()))
}

# Record the total amount of funding in the TGF scenario (across diseases and countries)
tot_tgf_funding = pd.Series({
    mapper_to_pretty_names[scenario_name]: sum(list(map(lambda x: x.df['value'].sum(), scenario_obj.values())))
    for scenario_name, scenario_obj in gf_scenarios.items()
}, name='TGF Funding').sort_index()

# "Thin-out" these scenarios to make the initial run go faster and to not use any unnecessary scenarios
# - Drop all 'incUnalloc' amounts
scenarios_to_run = {
    k: v for k, v in gf_scenarios.items()
    if not k.endswith('_incUnalloc')
}
# - Don't run every scenario
thinning_factor = 3  # 1 implies no thinning
scenarios_to_run = {
    k: v for i, (k, v) in enumerate(scenarios_to_run.items()) if i % thinning_factor == 0
}

#%% Declare assumptions that are not going to change in the analysis
NON_TGF_FUNDING = '_nonFubgible_dipiBase.csv'
parameters = Parameters(project_root / "src" / "scripts" / "ic7" / "shared" / "parameters.toml")

#%% Load the databases for HIV, Tb and Malaria
hiv_db = get_hiv_database()
tb_db = get_tb_database()
malaria_db = get_malaria_database()

# %% Function for running batch of analyses for all the funding scenarios for the LHS figure

def get_projections(
        approach: Literal['a', 'b'] = 'a',
        tgf_funding_scenario: str = '',
        innovation_on: bool = False,
        gp: bool = False
) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Returns Dict of portfolio results (itself a dict of the form {indicator: dataframe of results}, keyed by disease.
     As this must work for GP and model results, we only return the portfolio results (GP is not defined at the country
     level here)."""

    # Create Analysis objects for this funding scenario
    analysis_hiv = Analysis(
        database=hiv_db,
        tgf_funding=gf_scenarios[tgf_funding_scenario]['hiv'],
        non_tgf_funding=NonTgfFunding(funding_path / 'hiv' / 'non_tgf' / f'hiv{NON_TGF_FUNDING}'),
        parameters=parameters,
    )
    analysis_tb = Analysis(
        database=tb_db,
        tgf_funding=gf_scenarios[tgf_funding_scenario]['tb'],
        non_tgf_funding=NonTgfFunding(funding_path / 'tb' / 'non_tgf' / f'tb{NON_TGF_FUNDING}'),
        parameters=parameters,
    )
    analysis_malaria = Analysis(
        database=malaria_db,
        tgf_funding=gf_scenarios[tgf_funding_scenario]['malaria'],
        non_tgf_funding=NonTgfFunding(funding_path / 'malaria' / 'non_tgf' / f'malaria{NON_TGF_FUNDING}'),
        parameters=parameters,
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
                hiv=analysis_hiv.portfolio_projection_approach_b().portfolio_results,
                tb=analysis_tb.portfolio_projection_approach_b().portfolio_results,
                malaria=analysis_malaria.portfolio_projection_approach_b().portfolio_results
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


# %% Analysis for LEFT-HAND-SIDE Plot
if DO_RUN:
    Results_LHS = dict()
    for scenario_label in scenarios_to_run:
        Results_LHS[scenario_label] = get_projections(approach='a', innovation_on=False,
                                                      tgf_funding_scenario=scenario_label)

    # Now produce the variations on this that are required.
    Results_LHS['$11Bn: With Innovation'] = get_projections(approach='a', innovation_on=True,
                                                            tgf_funding_scenario='Fubgible_gf_11b')

    Results_LHS['$11Bn: Incl. Unalloc'] = get_projections(approach='a', innovation_on=False,
                                                          tgf_funding_scenario='Fubgible_gf_11b_incUnalloc')

    Results_LHS['$11Bn: Approach B'] = get_projections(approach='b', innovation_on=False,
                                                       tgf_funding_scenario='Fubgible_gf_11b')

    Results_LHS['$11Bn: Approach B & Incl. Unalloc'] = get_projections(approach='b', innovation_on=False,
                                                                       tgf_funding_scenario='Fubgible_gf_11b_incUnalloc')

    Results_LHS['$11Bn: Approach B & With Innovation'] = get_projections(approach='b', innovation_on=True,
                                                                         tgf_funding_scenario='Fubgible_gf_11b')

    Results_LHS['$11Bn: Approach B & Incl. Unalloc & With Innovation'] = get_projections(approach='b', innovation_on=True,
                                                                                         tgf_funding_scenario='Fubgible_gf_11b_incUnalloc')

    Results_LHS['GP'] = get_projections(gp=True, approach='a', innovation_on=False, tgf_funding_scenario='Fubgible_gf_11b')

    save_var(Results_LHS, get_root_path() / "sessions" / "Results_LHS.pkl")
else:
    Results_LHS = load_var(get_root_path() / "sessions" / "Results_LHS.pkl")


# %% Construct statistics for LHS plot

def get_percent_reduction_from_2022_to_2030(_results, indicator: str) -> pd.DataFrame:
    """Find the percentage reduction in the indicator from 2022 to 2030.
    :param: `indicator` might be 'cases' or 'deaths' or another indicator."""
    s = defaultdict(dict)
    for disease in ('hiv', 'tb', 'malaria'):
        for scenario in _results:
            s[disease][scenario] = 100 * (1.0 - (
                    _results[scenario][disease][indicator].at[2030, 'model_central'] /
                    _results[scenario][disease][indicator].at[2022, 'model_central']
            ))
    return pd.DataFrame(s)


def get_sum_of_indicator_during_2022_to_2030_as_percent_of_gp(_results, indicator: str) -> pd.DataFrame:
    """Find the value of the indicator, summed in the period 2022-2030, relative to the value in GP.
    :param: `indicator` might be 'cases' or 'deaths' or another indicator."""
    s = defaultdict(dict)
    for disease in ('hiv', 'tb', 'malaria'):
        gp_total = _results['GP'][disease][indicator].loc[slice(2022, 2030)]['model_central'].sum()
        for scenario in _results:
            scenario_total = _results[scenario][disease][indicator].loc[slice(2022, 2030)]['model_central'].sum()
            s[disease][scenario] = 100 * (scenario_total / gp_total)
    return pd.DataFrame(s)


def get_percent_reduction_in_indicator_from_2030_vs_2022_relative_to_gp(r, indicator: str) -> pd.DataFrame:
    """Find the percentage of the reduction that is achieved in each result, relative to GP.
    e.g., if GP reduces cases by 80% from 2022 to 2030, and the scenario reduces cases by 40%: the result is 50%
    :param: `indicator` might be 'cases' or 'deaths' or another indicator.
    """
    s = defaultdict(dict)
    for disease in ('hiv', 'tb', 'malaria'):
        gp_reduction = 1.0 - (
                r['GP'][disease][indicator].at[2030, 'model_central'] / r['GP'][disease][indicator].at[2022, 'model_central']
        )
        for scenario in r:
            scenario_reduction = 1.0 - (
                        r[scenario][disease][indicator].at[2030, 'model_central'] / r['GP'][disease][indicator].at[2022, 'model_central']
            )
            s[disease][scenario] = 100 * scenario_reduction / gp_reduction
    return pd.DataFrame(s)


stats = {
    'cases_percent_reduction_2022_to_2030': get_percent_reduction_from_2022_to_2030(Results_LHS, indicator='cases'),
    'deaths_percent_reduction_2022_to_2030': get_percent_reduction_from_2022_to_2030(Results_LHS, indicator='deaths'),
    'cases_relative_to_gp': get_sum_of_indicator_during_2022_to_2030_as_percent_of_gp(Results_LHS, indicator='cases'),
    'deaths_relative_to_gp': get_sum_of_indicator_during_2022_to_2030_as_percent_of_gp(Results_LHS, indicator='deaths'),
    'cases_reduction_vs_gp': get_percent_reduction_in_indicator_from_2030_vs_2022_relative_to_gp(Results_LHS, indicator='cases'),
    'deaths_reduction_vs_gp': get_percent_reduction_in_indicator_from_2030_vs_2022_relative_to_gp(Results_LHS, indicator='deaths'),
}

# Add the combination one: across cases and deaths and all disease
stats['cases_and_deaths_reduction_vs_gp'] = (stats['cases_reduction_vs_gp'] + stats['deaths_reduction_vs_gp']) / 2  # Gives equal weighting to reduction in cases and deaths
stats['cases_and_deaths_reduction_vs_gp']['all'] = stats['cases_and_deaths_reduction_vs_gp'].mean(axis=1)  # Gives equal weighting to all diseases

# %% Make the LHS-type figures

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
    fig.savefig(project_root / 'outputs' / f"mehran_lhs_fig_{title}.png")
    fig.tight_layout()
    fig.show()
    plt.close(fig)


# Make graphs for LHS-type figures
# Headline graph of the combined reduction in cases and deaths across all diseases
make_graph(
    stats['cases_and_deaths_reduction_vs_gp']['all'],
    title='Percent of GP Reduction in Cases and Deaths- All Diseases',
)

# Graph for each permutation of statistic and disease.
for stat in stats:
    for disease in ('hiv', 'tb', 'malaria'):
        make_graph(
            stats[stat][disease],
            title=f'{stat}- {disease}',
        )

# Explore time-trend
for disease in ('hiv', 'tb', 'malaria'):
    for indicator in ('cases', 'deaths'):
        time_trend = pd.DataFrame({scenario: Results_LHS[scenario][disease][indicator]['model_central'] for scenario in Results_LHS})
        time_trend[['GP', 'Fubgible_gf_11b', '$11Bn: With Innovation', 'Fubgible_gf_20b', ]].plot()
        plt.title(f'{disease}: {indicator}')
        plt.show()


# %% RHS figure

# - Define some additional scenarios to run for the TGF Ask from $0 up to enough that the full GP can be funded.
def make_tgf_funding_scenario(total: int, based_on: TgfFunding) -> TgfFunding:
    """Make a TGF funding object that resembles the one provided in `based_on`, but which is edited so that the
    total funding amount totals `total` and is distributed evenly across the countries."""
    assert isinstance(total, int)
    df = based_on.df.copy()
    df.loc[:, 'value'] = total / len(df)
    df['value'] = df['value'].astype(int)
    df.loc[df.index[0], 'value'] += total - df['value'].sum()  # add under-count (due to rounding) to the first country
    assert df['value'].sum() == total
    return TgfFunding.from_df(df)


# For each disease, work out what amount of TGF funding will lead to full-funding
slice_yrs_for_funding = slice(parameters.get('YEARS_FOR_FUNDING')[0], parameters.get('YEARS_FOR_FUNDING')[-1])
gp_amt = {
    'hiv': hiv_db.model_results.df.loc[('GP_GP', 1.0, slice(None), slice_yrs_for_funding, 'cost'), 'central'].groupby(
        'country').sum(),
    'tb': tb_db.model_results.df.loc[('GP_GP', 1.0, slice(None), slice_yrs_for_funding, 'cost'), 'central'].groupby(
        'country').sum(),
    'malaria': malaria_db.model_results.df.loc[
        ('GP_GP', 1.0, slice(None), slice_yrs_for_funding, 'cost'), 'central'].groupby('country').sum(),
}
non_tgf_funding_amt = {
    'hiv': NonTgfFunding(funding_path / 'hiv' / 'non_tgf' / f'hiv{NON_TGF_FUNDING}').df['value'],
    'tb': NonTgfFunding(funding_path / 'tb' / 'non_tgf' / f'tb{NON_TGF_FUNDING}').df['value'],
    'malaria': NonTgfFunding(funding_path / 'malaria' / 'non_tgf' / f'malaria{NON_TGF_FUNDING}').df['value'],
}
unfunded_amount = {
    # Gap for each disease between Non_TGF sources and the GP scenario (summed across country)
    'hiv': (gp_amt['hiv'] - non_tgf_funding_amt['hiv']).clip(lower=0).sum(),
    'tb': (gp_amt['tb'] - non_tgf_funding_amt['tb']).clip(lower=0).sum(),
    'malaria': (gp_amt['malaria'] - non_tgf_funding_amt['malaria']).clip(lower=0).sum(),
}

# Create a range of scenarios that, for each disease, span TGF Funding from $0 to the amount required to give full funding
# key for the scenario name is:
#   (
#       Pretty-name-of-scenario if it's an actual defined scenario (None otherwise),
#       Funding Fraction
#   )

num_new_scenarios = 5  # increase this for more points
tgf_scenarios_for_rhs_plot = {
    disease: {
        (None, round((x + non_tgf_funding_amt[disease].sum()) / gp_amt[disease].sum(), 3)):
            make_tgf_funding_scenario(int(x), based_on=gf_scenarios['Fubgible_gf_11b'][disease])
        for x in np.linspace(100e6, unfunded_amount[disease], num_new_scenarios)
    }
    for disease in ('hiv', 'tb', 'malaria')
}

# add in the defined tgf scenarios (the ones specified in the files)
for disease in ('hiv', 'tb', 'malaria'):
    tgf_scenarios_for_rhs_plot[disease].update(
        {
            (mapper_to_pretty_names[b],
             (scenarios_to_run[b][disease].df['value'].sum() + non_tgf_funding_amt[disease].sum()) / gp_amt[disease].sum()): scenarios_to_run[b][disease]
            for b in scenarios_to_run.keys()
        }
    )


def get_approach_b_projection(tgf_funding_scenario: TgfFunding, disease: str) -> Dict[str, pd.DataFrame]:
    if disease == 'hiv':
        db = hiv_db
    elif disease == 'tb':
        db = tb_db
    elif disease == 'malaria':
        db = malaria_db
    else:
        raise ValueError

    analysis = Analysis(
        database=db,
        tgf_funding=tgf_funding_scenario,
        non_tgf_funding=NonTgfFunding(funding_path / disease / 'non_tgf' / f'{disease}{NON_TGF_FUNDING}'),
        parameters=parameters,
    )
    return analysis.portfolio_projection_approach_b().portfolio_results


if DO_RUN:
    # Run all these scenarios under Approach B for each disease
    Results_RHS = defaultdict(dict)
    for disease in ('hiv', 'tb', 'malaria'):
        for fraction_of_gp_total_funding, tgf_funding_scenario in tgf_scenarios_for_rhs_plot[disease].items():
            Results_RHS[disease][fraction_of_gp_total_funding] = get_approach_b_projection(
                tgf_funding_scenario=tgf_funding_scenario, disease=disease)

    save_var(Results_RHS, get_root_path() / "sessions" / "Results_RHS.pkl")
else:
    Results_RHS = load_var(get_root_path() / "sessions" / "Results_RHS.pkl")

# %% Produce summary graphic

# - Fraction of the GP reduction achieved in cases and deaths
# NB. Sometimes the results undershoot/overshoot the GP because neither the model results under Approach B nor the GP is trying to maximise this metric.
for disease in ('hiv', 'tb', 'malaria'):
    to_plot = list()
    reduc_in_cases_under_gp = (1.0 - Results_LHS['GP'][disease]['cases'].at[2030, 'model_central'] / Results_LHS['GP'][disease]['cases'].at[2022, 'model_central'])
    reduc_in_deaths_under_gp = (1.0 - Results_LHS['GP'][disease]['deaths'].at[2030, 'model_central'] / Results_LHS['GP'][disease]['deaths'].at[2022, 'model_central'])

    for (scenario_name, funding_fraction), _res in Results_RHS[disease].items():

        reduction_in_cases_vs_gp = (1.0 - (_res['cases'].at[2030, 'model_central'] / Results_LHS['GP'][disease]['cases'].at[2022, 'model_central'])) / reduc_in_cases_under_gp
        reduction_in_deaths_vs_gp = (1.0 - (_res['deaths'].at[2030, 'model_central'] / Results_LHS['GP'][disease]['deaths'].at[2022, 'model_central'])) / reduc_in_cases_under_gp
        average_reduction_in_cases_and_deaths_vs_gp = (reduction_in_cases_vs_gp + reduction_in_deaths_vs_gp) / 2.  # Equal weighting to cases and deaths

        to_plot.extend([dict(
            scenario_name=scenario_name if scenario_name is not None else '',
            funding_fraction=100 * funding_fraction,
            reduction_in_cases=100 * reduction_in_cases_vs_gp,
            reduction_in_deaths=100 * reduction_in_deaths_vs_gp,
            average_reduction_in_cases_and_deaths_vs_gp=100 * average_reduction_in_cases_and_deaths_vs_gp
        )])

    to_plot = pd.DataFrame.from_records(to_plot).sort_values(by='funding_fraction', ascending=True)

    fig, ax = plt.subplots(nrows=1, ncols=3, sharey=True, sharex=True)
    real_points = to_plot.loc[to_plot['scenario_name'].str.len() > 0]

    for _ax, _column, _title in zip(
            ax,
            ['reduction_in_cases', 'reduction_in_deaths', 'average_reduction_in_cases_and_deaths_vs_gp'],
            ['cases', 'deaths', 'both']
    ):
        _ax.plot(to_plot['funding_fraction'],
                to_plot[_column],
                label=None, marker='o', markersize=5, color='black', linestyle='--')
        for _, _real_pt in real_points.iterrows():
            _ax.plot(_real_pt['funding_fraction'],
                    _real_pt[_column],
                    label=_real_pt.scenario_name,
                    marker='o', markersize=10, linestyle='')
        _ax.set_xlabel('Fraction of GP Funded (%)')
        _ax.set_ylabel('Progress to GP 2030 target (%')
        _ax.set_xlim(0, 120)
        _ax.set_title(_title)
        _ax.axhline(y=100, linestyle='--', color='grey')
        _ax.set_ylim(bottom=0.)
        _ax.legend(fontsize=8, loc='lower left')

    fig.suptitle(f'Impact For Approach B: {disease}')
    fig.tight_layout()
    fig.show()
    fig.savefig(project_root / 'outputs' / f"mehran_rhs_fig_cases_and_death_reduction_relative_to_gp_{disease}.png")
    plt.close(fig)



#%% - Cases and death in the period 2023-2030, divided by the number achieved in GP (lower is better).
for disease in ('hiv', 'tb', 'malaria'):
    to_plot = list()

    cases_2022_to_2030_gp = Results_LHS['GP'][disease]['cases'].loc[slice(2023, 2030), 'model_central'].sum()
    deaths_2022_to_2030_gp = Results_LHS['GP'][disease]['deaths'].loc[slice(2023, 2030), 'model_central'].sum()

    for (scenario_name, funding_fraction), _res in Results_RHS[disease].items():

        cases_2022_to_2030 = _res['cases'].loc[slice(2023, 2030), 'model_central'].sum() / cases_2022_to_2030_gp
        deaths_2022_to_2030 = _res['deaths'].loc[slice(2023, 2030), 'model_central'].sum() / deaths_2022_to_2030_gp
        average_reduction_in_cases_and_deaths_vs_gp = (cases_2022_to_2030 + deaths_2022_to_2030) / 2.

        to_plot.extend([dict(
            scenario_name=scenario_name if scenario_name is not None else '',
            funding_fraction=100 * funding_fraction,
            reduction_in_cases=100 * cases_2022_to_2030,
            reduction_in_deaths=100 * deaths_2022_to_2030,
            average_reduction_in_cases_and_deaths_vs_gp=100 * average_reduction_in_cases_and_deaths_vs_gp
            )])

    to_plot = pd.DataFrame.from_records(to_plot).sort_values(by='funding_fraction', ascending=True)

    fig, ax = plt.subplots(nrows=1, ncols=3, sharey=True, sharex=True)
    real_points = to_plot.loc[to_plot['scenario_name'].str.len() > 0]

    for _ax, _column, _title in zip(
            ax,
            ['reduction_in_cases', 'reduction_in_deaths', 'average_reduction_in_cases_and_deaths_vs_gp'],
            ['cases', 'deaths', 'both']
    ):
        _ax.plot(to_plot['funding_fraction'],
                to_plot[_column],
                label=None, marker='o', markersize=5, color='black', linestyle='--')
        for _, _real_pt in real_points.iterrows():
            _ax.plot(_real_pt['funding_fraction'],
                    _real_pt[_column],
                    label=_real_pt.scenario_name,
                    marker='o', markersize=10, linestyle='')
        _ax.set_xlabel('Fraction of GP Funded (%)')
        _ax.set_ylabel('Cases and Deaths 2023-2030 / That in GP (%)')
        _ax.set_xlim(0, 105)
        _ax.set_title(_title)
        _ax.axhline(y=100, linestyle='--', color='grey')
        _ax.set_ylim(bottom=0.)
        _ax.legend(fontsize=8, loc='lower left')

    fig.suptitle(f'Impact For Approach B: {disease}')
    fig.tight_layout()
    fig.show()
    fig.savefig(project_root / 'outputs' / f"mehran_rhs_fig_cases_and_death_divided_by_gp_{disease}.png")
    plt.close(fig)

