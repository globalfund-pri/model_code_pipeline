"""
This script produces the analysis that shows the Impact that can achieved for each Global Fund budget scenario, under
Approach B. (aka. RHS-version of Mehran's Figures)
"""

from collections import defaultdict
from typing import Dict

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from scripts.ic8.hiv.hiv_analysis import get_hiv_database
from scripts.ic8.malaria.malaria_analysis import get_malaria_database
from scripts.ic8.tb.tb_analysis import get_tb_database
from tgftools.analysis import Analysis
from tgftools.filehandler import (
    NonTgfFunding,
    Parameters,
    TgfFunding,
)
from tgftools.utils import (
    get_data_path,
    get_root_path,
    save_var,
    load_var,
)

# Declare paths
project_root = get_root_path()
path_to_data_folder = get_data_path()


# %% Flag to indicate whether the script should reload model results from raw files and/or re-run all the analysis, or
# instead to re-load locally-cached versions of `ModelResults` binaries and locally-cached version of the analysis
# results.
LOAD_DATA = False
DO_RUN = True


#%% Declare assumptions that are not going to change in the analysis
SCENARIO_DESCRIPTOR = 'PF'
parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")


#%% Load the databases for HIV, Tb and Malaria
hiv_db = get_hiv_database(load_data_from_raw_files=LOAD_DATA)
tb_db = get_tb_database(load_data_from_raw_files=LOAD_DATA)
malaria_db = get_malaria_database(load_data_from_raw_files=LOAD_DATA)


#%% Load Finance Scenario Files
# N.B. This uses the paths of the currrent sharepoint files, but the sharepoint could be reorganised to make this easier.

funding_path = path_to_data_folder / 'IC8' / 'funding'

Scenarios = {
    '$17bn Scenario': {
        'tgf': {
            'hiv': TgfFunding(funding_path / '2024_11_24' / 'hiv' / 'tgf' / 'hiv_fung_inc_unalc_bs17.csv'),
            'tb': TgfFunding(funding_path / '2024_11_24' / 'tb' / 'tgf' / 'tb_fung_inc_unalc_bs17.csv'),
            'malaria': TgfFunding(funding_path / '2024_11_24' / 'malaria' / 'tgf' / 'malaria_fung_inc_unalc_bs17.csv'),
        },
        'non_tgf': {
            'hiv': NonTgfFunding(funding_path / '2024_11_24' / 'hiv' / 'non_tgf' / 'hiv_nonfung_base_c.csv'),
            'tb': NonTgfFunding(funding_path / '2024_11_24' / 'tb' / 'non_tgf' / 'tb_nonfung_base_c.csv'),
            'malaria': NonTgfFunding(funding_path / '2024_11_24' / 'malaria' / 'non_tgf' / 'malaria_nonfung_base_c.csv'),
        },
    },
    '$15bn Scenario': {
        'tgf': {
            'hiv': TgfFunding(funding_path / '2024_11_24_15bn' /  'hiv' / 'tgf' / 'hiv_fung_inc_unalc_bs15.csv'),
            'tb': TgfFunding(funding_path / '2024_11_24_15bn' / 'tb' / 'tgf' / 'tb_fung_inc_unalc_bs15.csv'),
            'malaria': TgfFunding(funding_path / '2024_11_24_15bn' / 'malaria' / 'tgf' / 'malaria_fung_inc_unalc_bs15.csv'),
        },
        'non_tgf': {
            'hiv': NonTgfFunding(funding_path / '2024_11_24_15bn' / 'hiv' / 'non_tgf' / 'hiv_nonfung_base_c.csv'),
            'tb': NonTgfFunding(funding_path / '2024_11_24_15bn' / 'tb' / 'non_tgf' / 'tb_nonfung_base_c.csv'),
            'malaria': NonTgfFunding(funding_path / '2024_11_24_15bn' / 'malaria' / 'non_tgf' / 'malaria_nonfung_base_c.csv'),
        },
    }
}

# Check if the non-tgf values for both scenarios are the same
# todo - different countries in each!
Scenarios['$17bn Scenario']['tgf']['hiv'].df['value'] - Scenarios['$15bn Scenario']['tgf']['hiv'].df['value']



#%% Construct the scenarios to run - including new 'ficticious' scenarios Load TGF Funding Scenarios
gf_scenarios = {
    '$17bn Scenario': {
        'hiv': TgfFunding(funding_path / 'hiv' / 'tgf' / 'hiv_fung_inc_unalc_bs17.csv'),
        'tb': TgfFunding(funding_path / 'tb' / 'tgf' / 'tb_fung_inc_unalc_bs17.csv'),
        'malaria': TgfFunding(funding_path / 'malaria' / 'tgf' / 'malaria_fung_inc_unalc_bs17.csv'),
    }
}


#for 17bn
non_tgf_funding = {
    'hiv': NonTgfFunding(funding_path / 'hiv' / 'non_tgf' /'hiv_nonfung_base_c.csv'),
    'tb': NonTgfFunding(funding_path / 'tb' / 'non_tgf' / 'tb_nonfung_base_c.csv'),
    'malaria': NonTgfFunding(funding_path / 'malaria' / 'non_tgf' / 'malaria_nonfung_base_c.csv'),
}

non_tgf_funding_amt = {k: v.df['value'] for k, v in non_tgf_funding.items()}

# For each disease, work out what amount of TGF funding will lead to full-funding
slice_yrs_for_funding = slice(parameters.get('YEARS_FOR_FUNDING')[0], parameters.get('YEARS_FOR_FUNDING')[-1])

def get_cost_for_highest_cost_scenario_for_each_country(df: pd.DataFrame) -> pd.Series:
    """Returns the cost for the highest cost scenario for each country as pd.Series."""
    dfx = df.loc[(SCENARIO_DESCRIPTOR, slice(None), slice(None), slice_yrs_for_funding, 'cost'), 'central'].groupby(
        by=['country', 'funding_fraction']).sum()
    return dfx.loc[dfx.groupby(level=0).idxmax()]

gp_amt = {
    'hiv': get_cost_for_highest_cost_scenario_for_each_country(hiv_db.model_results.df),
    'tb': get_cost_for_highest_cost_scenario_for_each_country(tb_db.model_results.df),
    'malaria': get_cost_for_highest_cost_scenario_for_each_country(malaria_db.model_results.df),
}


unfunded_amount = {
    # Gap for each disease between Non_TGF sources and the GP scenario (summed across country)
    'hiv': (gp_amt['hiv'] - non_tgf_funding_amt['hiv']).clip(lower=0).sum(),
    'tb': (gp_amt['tb'] - non_tgf_funding_amt['tb']).clip(lower=0).sum(),
    'malaria': (gp_amt['malaria'] - non_tgf_funding_amt['malaria']).clip(lower=0).sum(),
}


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
            make_tgf_funding_scenario(int(x), based_on=gf_scenarios['$17bn Scenario'][disease])
        for x in np.linspace(100e6, unfunded_amount[disease], num_new_scenarios)
    }
    for disease in ('hiv', 'tb', 'malaria')
}

# add in the defined tgf scenarios (the ones specified in the files)
for disease in ('hiv', 'tb', 'malaria'):
    tgf_scenarios_for_rhs_plot[disease].update(
        {
            (b,
             (gf_scenarios[b][disease].df['value'].sum() + non_tgf_funding_amt[disease].sum()) / gp_amt[disease].sum()
             ): gf_scenarios[b][disease]
            for b in gf_scenarios.keys()
        }
    )

#%% Running the analyses


if DO_RUN:

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
            scenario_descriptor=SCENARIO_DESCRIPTOR,
            tgf_funding=tgf_funding_scenario,
            non_tgf_funding=non_tgf_funding[disease],
            parameters=parameters,
            handle_out_of_bounds_costs=True,
            innovation_on=False,
        )
        return analysis.portfolio_projection_approach_b(
            methods=['ga_backwards'],
            optimisation_params={
                'years_for_obj_func': parameters.get('YEARS_FOR_OBJ_FUNC'),
                'force_monotonic_decreasing': True
            }
        ).portfolio_results

    # Run all these scenarios under Approach B for each disease
    Results_RHS = defaultdict(dict)
    for disease in (
            'hiv',
            # 'tb',
            # 'malaria',
    ):
        for fraction_of_gp_total_funding, tgf_funding_scenario in tgf_scenarios_for_rhs_plot[disease].items():
            Results_RHS[disease][fraction_of_gp_total_funding] = get_approach_b_projection(
                tgf_funding_scenario=tgf_funding_scenario, disease=disease)

    save_var(Results_RHS, get_root_path() / "sessions" / "Results_RHS.pkl")
else:
    Results_RHS = load_var(get_root_path() / "sessions" / "Results_RHS.pkl")


# %% Produce graphic

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

    # cases_2022_to_2030_gp = Results_LHS['GP'][disease]['cases'].loc[slice(2023, 2030), 'model_central'].sum()
    # deaths_2022_to_2030_gp = Results_LHS['GP'][disease]['deaths'].loc[slice(2023, 2030), 'model_central'].sum()

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

