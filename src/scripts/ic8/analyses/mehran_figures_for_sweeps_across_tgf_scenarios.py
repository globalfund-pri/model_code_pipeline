"""
This script produces the analysis that shows the Impact that can achieved for each Global Fund budget scenario, under
Approach B. (aka. RHS-version of Mehran's Figures)
"""

from collections import defaultdict
from copy import copy
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
DO_RUN = False

#%% Declare assumptions that are not going to change in the analysis
SCENARIO_DESCRIPTOR = 'PF'
parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")


#%% Load the databases for HIV, Tb and Malaria
hiv_db = get_hiv_database(load_data_from_raw_files=LOAD_DATA)
tb_db = get_tb_database(load_data_from_raw_files=LOAD_DATA)
malaria_db = get_malaria_database(load_data_from_raw_files=LOAD_DATA)


#%% Load Finance Scenario Files
# N.B. This uses the paths of the currrent sharepoint files, but the sharepoint could be reorganised to make this (a lot!!) easier.

funding_path = path_to_data_folder / 'IC8' / 'funding'


def filter_funding_data_for_non_modelled_countries(funding_data_object: TgfFunding | NonTgfFunding, disease_name: str) -> TgfFunding | NonTgfFunding:
    """Returns a funding data object that has been filtered for countries that are not declared as the modelled
    countries for that disease."""
    list_of_modelled_countries = parameters.get_modelled_countries_for(disease_name.upper())
    funding_data_object = copy(funding_data_object)
    funding_data_object.df = funding_data_object.df[funding_data_object.df.index.isin(list_of_modelled_countries)]
    return funding_data_object

def make_tgf_funding_scenario(based_on: TgfFunding, total: int) -> TgfFunding:
    """Make a TGF funding object that resembles the one provided in `based_on`, but which is edited so that the
    total funding amount totals `total` and is distributed evenly across the countries."""
    assert isinstance(total, int)
    df = based_on.df.copy()
    df.loc[:, 'value'] = total / len(df)
    df['value'] = df['value'].astype(int)
    df.loc[df.index[0], 'value'] += total - df['value'].sum()  # add under-count (due to rounding) to the first country
    assert df['value'].sum() == total
    return TgfFunding.from_df(df)


Scenarios = {
    '$13bn Scenario': {
        'tgf': {
            'hiv': filter_funding_data_for_non_modelled_countries(
                TgfFunding(funding_path / '05-12-2024' / '13bn' / 'hiv' / 'budget_scenarios' / 'hiv_fung_inc_unalc_bs13.csv'), 'hiv'),
            'tb': filter_funding_data_for_non_modelled_countries(
                TgfFunding(funding_path / '05-12-2024' / '13bn' / 'tb' / 'budget_scenarios' / 'tb_fung_inc_unalc_bs13.csv'), 'tb'),
            'malaria': filter_funding_data_for_non_modelled_countries(
                TgfFunding(funding_path / '05-12-2024' / '13bn' / 'malaria' / 'budget_scenarios' / 'malaria_fung_inc_unalc_bs13.csv'), 'malaria'),
        },
        'non_tgf': {
            'hiv': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(funding_path / '05-12-2024' / '13bn' / 'hiv' / 'budget_scenarios' / 'hiv_nonfung_base_c.csv'), 'hiv'),
            'tb': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(funding_path / '05-12-2024' / '13bn' / 'tb' / 'budget_scenarios' / 'tb_nonfung_base_c.csv'), 'tb'),
            'malaria': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(funding_path / '05-12-2024' / '13bn' / 'malaria' / 'budget_scenarios' / 'malaria_nonfung_base_c.csv'), 'malaria'),
        },
    },
    '$15bn Scenario': {
        'tgf': {
            'hiv': filter_funding_data_for_non_modelled_countries(
                TgfFunding(funding_path / '2024_11_24_15bn' / 'hiv' / 'tgf' / 'hiv_fung_inc_unalc_bs15.csv'), 'hiv'),
            'tb': filter_funding_data_for_non_modelled_countries(
                TgfFunding(funding_path / '2024_11_24_15bn' / 'tb' / 'tgf' / 'tb_fung_inc_unalc_bs15.csv'), 'tb'),
            'malaria': filter_funding_data_for_non_modelled_countries(
                TgfFunding(funding_path / '2024_11_24_15bn' / 'malaria' / 'tgf' / 'malaria_fung_inc_unalc_bs15.csv'), 'malaria'),
        },
        'non_tgf': {
            'hiv': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(funding_path / '2024_11_24_15bn' / 'hiv' / 'non_tgf' / 'hiv_nonfung_base_c.csv'), 'hiv'),
            'tb': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(funding_path / '2024_11_24_15bn' / 'tb' / 'non_tgf' / 'tb_nonfung_base_c.csv'), 'tb'),
            'malaria': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(funding_path / '2024_11_24_15bn' / 'malaria' / 'non_tgf' / 'malaria_nonfung_base_c.csv'), 'malaria'),
        },
    },
    '$17bn Scenario': {
        'tgf': {
            'hiv': filter_funding_data_for_non_modelled_countries(
                TgfFunding(funding_path / '2024_11_24' / 'hiv' / 'tgf' / 'hiv_fung_inc_unalc_bs17.csv'), 'hiv'),
            'tb': filter_funding_data_for_non_modelled_countries(
                TgfFunding(funding_path / '2024_11_24' / 'tb' / 'tgf' / 'tb_fung_inc_unalc_bs17.csv'), 'tb'),
            'malaria': filter_funding_data_for_non_modelled_countries(
                TgfFunding(funding_path / '2024_11_24' / 'malaria' / 'tgf' / 'malaria_fung_inc_unalc_bs17.csv'), 'malaria'),
        },
        'non_tgf': {
            'hiv': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(funding_path / '2024_11_24' / 'hiv' / 'non_tgf' / 'hiv_nonfung_base_c.csv'), 'hiv'),
            'tb': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(funding_path / '2024_11_24' / 'tb' / 'non_tgf' / 'tb_nonfung_base_c.csv'), 'tb'),
            'malaria': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(funding_path / '2024_11_24' / 'malaria' / 'non_tgf' / 'malaria_nonfung_base_c.csv'), 'malaria'),
        },
    },
    '$20bn Scenario': {
        'tgf': {
            'hiv': filter_funding_data_for_non_modelled_countries(
                TgfFunding(funding_path / '05-12-2024' / '20bn' / 'hiv' / 'budget_scenarios' / 'hiv_fung_inc_unalc_bs20.csv'), 'hiv'),
            'tb': filter_funding_data_for_non_modelled_countries(
                TgfFunding(funding_path / '05-12-2024' / '20bn' / 'tb' / 'budget_scenarios' / 'tb_fung_inc_unalc_bs20.csv'), 'tb'),
            'malaria': filter_funding_data_for_non_modelled_countries(
                TgfFunding(funding_path / '05-12-2024' / '20bn' / 'malaria' / 'budget_scenarios' / 'malaria_fung_inc_unalc_bs20.csv'), 'malaria'),
        },
        'non_tgf': {
            'hiv': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(funding_path / '05-12-2024' / '20bn' / 'hiv' / 'budget_scenarios' / 'hiv_nonfung_base_c.csv'), 'hiv'),
            'tb': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(funding_path / '05-12-2024' / '20bn' / 'tb' / 'budget_scenarios' / 'tb_nonfung_base_c.csv'), 'tb'),
            'malaria': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(funding_path / '05-12-2024' / '20bn' / 'malaria' / 'budget_scenarios' / 'malaria_nonfung_base_c.csv'), 'malaria'),
        },
    },
    'GP': {
        # This is based on a TGF ask amount that is enormous so that full-funding is met.
        'tgf': {
            'hiv': filter_funding_data_for_non_modelled_countries(
                make_tgf_funding_scenario(
                    TgfFunding(funding_path / '05-12-2024' / '20bn' / 'hiv' / 'budget_scenarios' / 'hiv_fung_inc_unalc_bs20.csv'), int(100e9)), 'hiv'),
            'tb': filter_funding_data_for_non_modelled_countries(
                make_tgf_funding_scenario(
                    TgfFunding(
                        funding_path / '05-12-2024' / '20bn' / 'tb' / 'budget_scenarios' / 'tb_fung_inc_unalc_bs20.csv'), int(100e9)), 'tb'),
            'malaria': filter_funding_data_for_non_modelled_countries(
                make_tgf_funding_scenario(
                    TgfFunding(
                        funding_path / '05-12-2024' / '20bn' / 'malaria' / 'budget_scenarios' / 'malaria_fung_inc_unalc_bs20.csv'), int(100e9)), 'malaria'),
        },
        'non_tgf': {
            'hiv': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(
                    funding_path / '05-12-2024' / '20bn' / 'hiv' / 'budget_scenarios' / 'hiv_nonfung_base_c.csv'),
                'hiv'),
            'tb': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(
                    funding_path / '05-12-2024' / '20bn' / 'tb' / 'budget_scenarios' / 'tb_nonfung_base_c.csv'), 'tb'),
            'malaria': filter_funding_data_for_non_modelled_countries(
                NonTgfFunding(
                    funding_path / '05-12-2024' / '20bn' / 'malaria' / 'budget_scenarios' / 'malaria_nonfung_base_c.csv'),
                'malaria'),
        },
    },
}


#%% For each scenario, and for each disease, work out the extent to which the GP need is met across whole portfolio

def get_cost_for_highest_cost_scenario_for_each_country(df: pd.DataFrame) -> pd.Series:
    """Returns the cost for the highest cost scenario for each country as pd.Series."""
    # For each disease, work out what amount of TGF funding will lead to full-funding
    slice_yrs_for_funding = slice(parameters.get('YEARS_FOR_FUNDING')[0], parameters.get('YEARS_FOR_FUNDING')[-1])
    dfx = df.loc[(SCENARIO_DESCRIPTOR, slice(None), slice(None), slice_yrs_for_funding, 'cost'), 'central'].groupby(
        by=['country', 'funding_fraction']).sum()
    return dfx.loc[dfx.groupby(level=0).idxmax()]

gp_amt = {
    'hiv': get_cost_for_highest_cost_scenario_for_each_country(hiv_db.model_results.df).sum(),
    'tb': get_cost_for_highest_cost_scenario_for_each_country(tb_db.model_results.df).sum(),
    'malaria': get_cost_for_highest_cost_scenario_for_each_country(malaria_db.model_results.df).sum(),
}

fraction_funded = defaultdict(dict)
for scenario_name in Scenarios.keys():
    for disease in ('hiv', 'tb', 'malaria'):
        total_funding = (Scenarios[scenario_name]['tgf'][disease].df['value'] + Scenarios[scenario_name]['non_tgf'][disease].df['value']).sum()
        fraction_funded[disease][scenario_name] = min(total_funding / gp_amt[disease], 1.0)


#%% Running the analyses


if DO_RUN:

    def get_approach_b_projection(
            tgf_funding_scenario: TgfFunding,
            non_tgf_funding_scenario: NonTgfFunding,
            disease: str,
    ) -> Dict[str, pd.DataFrame]:

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
            non_tgf_funding=non_tgf_funding_scenario,
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

    for scenario_name in Scenarios.keys():
        for disease in (
                'hiv',
                'tb',
                'malaria'
        ):
            Results_RHS[disease][scenario_name] = get_approach_b_projection(
                tgf_funding_scenario=Scenarios[scenario_name]['tgf'][disease],
                non_tgf_funding_scenario=Scenarios[scenario_name]['non_tgf'][disease],
                disease=disease)
    save_var(Results_RHS, get_root_path() / "sessions" / "Results_RHS.pkl")
else:
    Results_RHS = load_var(get_root_path() / "sessions" / "Results_RHS.pkl")


#%% Produce Graphic

YEARS_FOR_COMPARISON = slice(2027, 2029)

for disease in ('hiv', 'tb', 'malaria'):

    cases_gp = Results_RHS[disease]['GP']['cases'].loc[YEARS_FOR_COMPARISON, 'model_central'].sum()
    deaths_gp = Results_RHS[disease]['GP']['deaths'].loc[YEARS_FOR_COMPARISON, 'model_central'].sum()

    cases_vs_gp = dict()
    deaths_vs_gp = dict()
    cases_and_deaths_vs_gp = dict()

    for scenario in (sc for sc in Scenarios.keys() if sc != 'GP'):
        cases = Results_RHS[disease][scenario]['cases'].loc[YEARS_FOR_COMPARISON, 'model_central'].sum()
        deaths = Results_RHS[disease][scenario]['deaths'].loc[YEARS_FOR_COMPARISON, 'model_central'].sum()
        cases_vs_gp[scenario] = cases / cases_gp
        deaths_vs_gp[scenario] = deaths / deaths_gp
        cases_and_deaths_vs_gp[scenario] = ((cases / cases_gp) + (deaths / deaths_gp))/2

    to_plot = pd.concat({
        'funding_fraction': pd.Series({k: v for k, v in fraction_funded[disease].items() if k != 'GP'}),
        'cases_vs_gp': pd.Series(cases_vs_gp),
        'deaths_vs_gp': pd.Series(deaths_vs_gp),
        'cases_and_deaths_vs_gp': pd.Series(cases_and_deaths_vs_gp),
    }, axis=1).reset_index().set_index('funding_fraction').rename(columns={'index': 'scenario'})

    fig, ax = plt.subplots(ncols=3, sharex=True, sharey=True)
    for _ax, _indicator, _descriptor in zip(
            ax,
            ('cases_vs_gp', 'deaths_vs_gp', 'cases_and_deaths_vs_gp'),
            ('Cases', 'Deaths', 'Cases & Deaths')
    ):
        _ax.plot(100 * to_plot.index, 100 * to_plot[_indicator],
                marker='', linestyle='-', color='black')
        for ff, vals in to_plot.iterrows():
            _ax.plot(100 * ff, 100 * vals[_indicator],
                     label=vals['scenario'],
                     marker='o', markersize=10, linestyle='')
        _ax.legend(loc='best')
        _ax.set_xlabel('Fraction of GP Funded (%)')
        _ax.set_ylabel(f'{_descriptor} / That in GP (%)')
        _ax.set_xlim(50, 105)
        _ax.axhline(y=100, linestyle='--', color='grey')
        # _ax.set_ylim(bottom=99)
        _ax.legend(fontsize=8, loc='upper right')
    fig.suptitle(disease)
    fig.tight_layout()
    fig.show()
    plt.close(fig)
    fig.savefig(project_root / 'outputs' / f"mehran_rhs_fig_cases_and_death_divided_by_gp_{disease}.png")
