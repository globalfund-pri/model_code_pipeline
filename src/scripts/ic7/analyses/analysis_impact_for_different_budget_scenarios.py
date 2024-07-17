"""
This script produces the analysis that shows the Impact that can achieved for each Global Fund budget scenario, under
Approach A and Approach B.
"""
from pathlib import Path

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
    get_files_with_extension,
)

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

# "Thin-out" the scenarios to make the initial run go faster
# thinning_factor = 4
# scenarios = {
#     k: v for i, (k, v) in enumerate(scenarios.items()) if i % thinning_factor == 0
# }

# Load the databases for HIV, Tb and Malaria
# Declare the parameters, indicators and scenarios
parameters = Parameters(project_root / "src" / "scripts" / "ic7" / "shared" / "parameters.toml")

hiv_db = get_hiv_database(load_data_from_raw_files=False)
tb_db = get_tb_database(load_data_from_raw_files=False)
malaria_db = get_malaria_database(load_data_from_raw_files=False)

# Declare assumptions that are not going to change in the analysis
NON_TGF_FUNDING = '_nonFubgible_dipiBase.csv'
SCENARIO_DESCRIPTOR = 'IC_IC'

# For each scenario, do the analysis under Approach A and Approach B and compile the results
Results = dict()
for scenario_label, files in scenarios.items():

    # Create Analysis objects for this funding scenario
    analysis_hiv = Analysis(
        database=hiv_db,
        scenario_descriptor=SCENARIO_DESCRIPTOR,
        tgf_funding=TgfFunding(files['hiv']),
        non_tgf_funding=NonTgfFunding(funding_path / 'hiv' / 'non_tgf' / f'hiv{NON_TGF_FUNDING}'),
        parameters=parameters,
        handle_out_of_bounds_costs=True,
        innovation_on=True,
    )
    analysis_tb = Analysis(
        database=tb_db,
        scenario_descriptor=SCENARIO_DESCRIPTOR,
        tgf_funding=TgfFunding(files['tb']),
        non_tgf_funding=NonTgfFunding(funding_path / 'tb' / 'non_tgf' / f'tb{NON_TGF_FUNDING}'),
        parameters=parameters,
        handle_out_of_bounds_costs=True,
        innovation_on=True,
    )
    analysis_malaria = Analysis(
        database=tb_db,
        scenario_descriptor=SCENARIO_DESCRIPTOR,
        tgf_funding=TgfFunding(files['malaria']),
        non_tgf_funding=NonTgfFunding(funding_path / 'malaria' / 'non_tgf' / f'malaria{NON_TGF_FUNDING}'),
        parameters=parameters,
        handle_out_of_bounds_costs=True,
        innovation_on=True,
    )

    # Produce a report for this funding scenario under Approach A
    report_approach_a = HTMReport(
        hiv=analysis_hiv.portfolio_projection_approach_a(),
        tb=analysis_tb.portfolio_projection_approach_a(),
        malaria=analysis_malaria.portfolio_projection_approach_a(),
    )

    # Produce a report for this funding scenario under Approach B (greedy-algorithm-backwards)
    optimisation_params = {
        'years_for_obj_func': parameters.get('YEARS_FOR_OBJ_FUNC'),
        'force_monotonic_decreasing': True
    }
    report_approach_b = HTMReport(
        hiv=analysis_hiv.portfolio_projection_approach_b(methods=['ga_backwards'], optimisation_params=optimisation_params),
        tb=analysis_tb.portfolio_projection_approach_b(methods=['ga_backwards'], optimisation_params=optimisation_params),
        malaria=analysis_malaria.portfolio_projection_approach_a(),
        # todo: Couldn't get Approach B to work, as some countries that should be modelled were not in the results (e.g. COM), so using ApproachA as placeholder
        # malaria=analysis_malaria.portfolio_projection_approach_b(methods=['ga_backwards'], optimisation_params=optimisation_params),
    )

    # Define a summary measure of the results (could make any summary measure, or use one of the methods on `HTMReport`)
    def total_deaths_2020_to_2030(report: HTMReport) -> float:
        return (
            report.hiv.portfolio_results['deaths'].loc[slice(2020, 2030), 'model_central'].sum()
            + report.tb.portfolio_results['deaths'].loc[slice(2020, 2030), 'model_central'].sum()
            + report.malaria.portfolio_results['deaths'].loc[slice(2020, 2030), 'model_central'].sum()
        )

    # Store the results
    Results[scenario_label] = {
        'Approach A': total_deaths_2020_to_2030(report_approach_a),
        'Approach B': total_deaths_2020_to_2030(report_approach_b),
    }



#%% Make nice figure

# Give pretty names to the funding scenarios (and get order of the keys right)
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




# Check that the labels are correctly in ascending order
assert tot_tgf_funding.is_monotonic_increasing


Results_df = pd.DataFrame(Results).T
Results_df.index = Results_df.index.map(mapper_to_pretty_names)

formatted_to_plot = pd.concat([tot_tgf_funding, Results_df], axis=1)

def label_point(x, y, val, ax):
    a = pd.concat({'x': pd.Series(x), 'y': pd.Series(y), 'val': pd.Series(val)}, axis=1)
    for i, point in a.iterrows():
        ax.text(point['x'], point['y'], str(point['val']), fontsize=6)

fig, ax = plt.subplots()
formatted_to_plot.plot(x='TGF Funding', marker='.', linestyle='', ax=ax)
ax.set_ylabel('Total Deaths 2020-2030 (H+T+M)')
ax.set_xlabel('TGF Replenishment Scenario')
label_point(formatted_to_plot['TGF Funding'].values, formatted_to_plot['Approach A'].values, pd.Series(formatted_to_plot.index).values, ax=ax)
label_point(formatted_to_plot['TGF Funding'].values, formatted_to_plot['Approach B'].values, pd.Series(formatted_to_plot.index).values, ax=ax)
fig.tight_layout()
fig.show()
plt.close(fig)


fig, ax = plt.subplots()
tgf_funding_by_disease.plot(ax=ax, x='total', marker='.', linestyle='')
label_point(tgf_funding_by_disease['total'].values, tgf_funding_by_disease['hiv'].values, tgf_funding_by_disease.index.values, ax)
label_point(tgf_funding_by_disease['total'].values, tgf_funding_by_disease['tb'].values, tgf_funding_by_disease.index.values, ax)
label_point(tgf_funding_by_disease['total'].values, tgf_funding_by_disease['malaria'].values, tgf_funding_by_disease.index.values, ax)
ax.set_ylabel('TGF funding for each disease in budget file')
ax.set_xlabel('Total TGF funding across all diseases in budget file')
fig.tight_layout()
fig.show()
plt.close(fig)
