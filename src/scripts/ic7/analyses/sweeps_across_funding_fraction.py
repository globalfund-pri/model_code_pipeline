"""This figure showing the impact achieved if each country has the same proportion of its GP covered.
We do this by running the analysis in Approach C."""

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from scripts.ic7.hiv.hiv_analysis import get_hiv_database
from scripts.ic7.malaria.malaria_analysis import get_malaria_database
from scripts.ic7.tb.tb_analysis import get_tb_database
from tgftools.analysis import Analysis
from tgftools.filehandler import (
    Parameters,
)
from tgftools.utils import (
    get_data_path,
    get_root_path,
    save_var, load_var,
)

DO_RUN = False

# Declare paths
project_root = get_root_path()
path_to_data_folder = get_data_path()

#%% Declare assumptions that are not going to change in the analysis
NON_TGF_FUNDING = '_nonFubgible_dipiBase.csv'
parameters = Parameters(project_root / "src" / "scripts" / "ic7" / "shared" / "parameters.toml")

# Load the databases
hiv_db = get_hiv_database()
tb_db = get_tb_database()
malaria_db = get_malaria_database()


def get_analysis(disease: str) -> Analysis:
    if disease == 'hiv':
        db = hiv_db
    elif disease == 'tb':
        db = tb_db
    elif disease == 'malaria':
        db = malaria_db
    else:
        raise ValueError

    return Analysis(
        database=db,
        tgf_funding=None,
        non_tgf_funding=None,
        parameters=parameters,
    )


if DO_RUN:
    num_steps = 5
    Results = dict()
    for disease in ('hiv', 'tb', 'malaria', ):
        analysis = get_analysis(disease)
        Results[disease] = {ff: analysis.portfolio_projection_approach_c(ff) for ff in np.linspace(0.30, 1.0, num_steps)}
    save_var(Results, get_root_path() / "sessions" / "Results_SweepAcrossFundingFraction.pkl")
else:
    Results = load_var(get_root_path() / "sessions" / "Results_SweepAcrossFundingFraction.pkl")


#%% Make Graph

# get total cases and total deaths in the period 2023-2030
to_plot = list()
for disease in ('hiv', 'tb', 'malaria'):
    for funding_fraction in Results[disease]:
        to_plot.extend([
            dict(
                disease=disease,
                funding_fraction=100 * funding_fraction,
                total_cases=Results[disease][funding_fraction].portfolio_results['cases'].loc[slice(2022, 2030), 'model_central'].sum(),
                total_deaths=Results[disease][funding_fraction].portfolio_results['deaths'].loc[slice(2022, 2030), 'model_central'].sum(),
            )]
        )
to_plot = pd.DataFrame.from_records(to_plot).sort_values(by='funding_fraction', ascending=True)

for disease in ('hiv', 'tb', 'malaria'):
    fig, ax = plt.subplots(nrows=1, ncols=2, sharey=False, sharex=True)
    for _ax, _column, _title in zip(ax, ['total_cases', 'total_deaths'], ['cases 2022-2030', 'deaths 2022-2030',]):
        to_plot.loc[to_plot.disease == disease].plot(x='funding_fraction', y=_column, ax=_ax)
        _ax.set_xlabel("Fraction of All Countries' GP Funded (%)\n (Same in each country)")
        _ax.set_xlim(0, 100)
        _ax.set_title(_title)
        _ax.set_ylim(bottom=0.)
        _ax.legend(fontsize=8, loc='lower left')

    fig.suptitle(f'Impact For Approach C: {disease}')
    fig.tight_layout()
    fig.show()
    fig.savefig(project_root / 'outputs' / f"mehran_appr_c_{disease}.png")
    plt.close(fig)







