from pathlib import Path

import pandas as pd

from scripts.ic8.tb.tb_checks import DatabaseChecksTb
from scripts.ic8.tb.tb_filehandlers import PartnerDataTb, PFInputDataTb, ModelResultsTb, GpTb
from tgftools.FilePaths import FilePaths
from tgftools.analysis import Analysis
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

"""
This is a simple piece of code that utilizes the analysis class to generate the IC time series for TB up to 2035.  
This code is not part of the modular framework. 

This script holds everything relating to processing the model output. 
It contains information on: 
- The location of the parameter file, including aspects of the analysis such as objector function years, funding years, 
  whether to handle out of bounds, which scenario to run, etc
- The location of all the filepaths to be used, i.e.  which model data, pf data, partner data, and funding information

It also sets the following options: 
- Whether to load the model output from raw (see LOAD_DATA_FROM_RAW_FILES at the bottom of the file). 
  CAUTION: Updated to the filehandler relating to model output will not be reflected if this option is set to "False". 
- Whether to run checks or not (see DO_CHECKS at the bottom of the file) and, if checks are to be run, where to save the
  report of the checks. 

NOTE: Scenarios for the various counterfactuals are set in the main results for IC script
"""


def get_tb_database_2035(load_data_from_raw_files: bool = True) -> Database:

    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    if load_data_from_raw_files:
        # Load the files
        model_results = ModelResultsTb(
            filepaths.get('tb', 'model-results'),
            parameters=parameters,
        )
        # Save the model_results object
        save_var(model_results, project_root / "sessions" / "tb_model_data_2035_ic8.pkl")
    else:
        # Load the model results
        model_results = load_var(project_root / "sessions" / "tb_model_data_2035_ic8.pkl")

    # Load the files
    pf_input_data = PFInputDataTb(filepaths.get('tb', 'pf-input-data'), parameters=parameters)
    partner_data = PartnerDataTb(filepaths.get('tb', 'partner-data'), parameters=parameters)
    fixed_gp = FixedGp(filepaths.get('malaria', 'gp-data'), parameters=parameters)

    gp = GpTb(
        fixed_gp=fixed_gp,
        model_results=model_results,
        partner_data=partner_data,
        parameters=parameters,
    )

    # Create and return the database
    return Database(
        model_results=model_results,
        gp=gp,
        pf_input_data=pf_input_data,
        partner_data=partner_data,
    )


def get_tb_analysis_2035(
        load_data_from_raw_files: bool = True,
        do_checks: bool = False,
) -> Analysis:
    """Return the Analysis object for TB."""

    # Declare the parameters and filepaths
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    db = get_tb_database_2035(load_data_from_raw_files=load_data_from_raw_files)

    # Run the checks
    if do_checks:
        DatabaseChecksTb(
            db=db,
            parameters=parameters
        ).run(
            suppress_error=True,
            filename=project_root / "outputs" / "tb_report_of_checks_ic8.pdf"
        )

    # Load assumption for budgets for this analysis
    tgf_funding = TgfFunding(filepaths.get('tb', 'tgf-funding'))

    list = parameters.get_modelled_countries_for('TB')
    tgf_funding.df = tgf_funding.df[tgf_funding.df.index.isin(list)]

    non_tgf_funding = NonTgfFunding(filepaths.get('tb', 'non-tgf-funding'))
    non_tgf_funding.df = non_tgf_funding.df[non_tgf_funding.df.index.isin(list)]

    # Change end year
    parameters.int_store['END_YEAR'] = 2035

    return Analysis(
            database=db,
            tgf_funding=tgf_funding,
            non_tgf_funding=non_tgf_funding,
            parameters=parameters,
        )


if __name__ == "__main__":
    LOAD_DATA_FROM_RAW_FILES = True
    DO_CHECKS = False

    # Create the Analysis object
    analysis = get_tb_analysis_2035(
        load_data_from_raw_files=LOAD_DATA_FROM_RAW_FILES,
        do_checks=DO_CHECKS
    )

    # Get the finalised Set of Portfolio Projections (decided upon IC scenario and Counterfactual):
    from scripts.ic8.analyses.main_results_for_investment_case import get_set_of_portfolio_projections
    pps = get_set_of_portfolio_projections(analysis)

    # Get results out from this set for the graph
    tb_cases = pd.DataFrame(
            index=pd.Index(list(range(2010, 2036)), name='Year'),
            data={
                'Actual': pps.PARTNER['cases'],
                'GP': pps.CF_forgraphs['cases'],
                'Counterfactual': pps.CF_InfAve.portfolio_results['cases']['model_central'],
                'IC': pps.IC.portfolio_results['cases']['model_central'],
                'IC_LB': pps.IC.portfolio_results['cases']['model_low'],
                'IC_UB': pps.IC.portfolio_results['cases']['model_high'],
                'pop_actual': pps.PARTNER['population'],
                'pop_cf': pps.CF_InfAve.portfolio_results['population']['model_central'],
                'pop_ic': pps.IC.portfolio_results['population']['model_central'],
                'Actual_inc': pps.PARTNER['cases'] / pps.PARTNER["population"],
                'GP_inc': pps.CF_forgraphs['incidence'],
                'CF_inc': pps.CF_InfAve.portfolio_results['cases']['model_central'] /
                          pps.CF_InfAve.portfolio_results['population']['model_central'],
                'IC_inc': pps.IC.portfolio_results['cases']['model_central'] /
                          pps.IC.portfolio_results['population']['model_central'],
                'IC_LB_inc': pps.IC.portfolio_results['cases']['model_low'] /
                             pps.IC.portfolio_results['population']['model_central'],
                'IC_UB_inc': pps.IC.portfolio_results['cases']['model_high'] /
                             pps.IC.portfolio_results['population']['model_central'],
                'IC_LB_adj': (pps.IC.portfolio_results['cases']['model_low'])*0.9,
                'IC_UB_adj': (pps.IC.portfolio_results['cases']['model_high'])*1.1,
            }
        )

    # Save df
    path_to_sessions_folder = get_root_path() / 'sessions'
    tb_cases.to_csv(path_to_sessions_folder / 'tb_cases_2035.csv')

    tbh_deaths = pd.DataFrame(
        index=pd.Index(list(range(2010, 2036)), name='Year'),
        data={
            'Actual': pps.PARTNER['deaths'],
            'GP': pps.CF_forgraphs['deaths'],
            'Counterfactual': pps.CF_InfAve.portfolio_results['deaths']['model_central'],
            'IC': pps.IC.portfolio_results['deaths']['model_central'],
            'IC_LB': pps.IC.portfolio_results['deaths']['model_low'],
            'IC_UB': pps.IC.portfolio_results['deaths']['model_high'],
            'pop_actual': pps.PARTNER['population'],
            'pop_cf': pps.CF_InfAve.portfolio_results['population']['model_central'],
            'pop_ic': pps.IC.portfolio_results['population']['model_central'],
            'Actual_inc': pps.PARTNER['deaths'] / pps.PARTNER["population"],
            'GP_inc': pps.CF_forgraphs['mortality'],
            'CF_inc': pps.CF_InfAve.portfolio_results['deaths']['model_central'] /
                      pps.CF_InfAve.portfolio_results['population']['model_central'],
            'IC_inc': pps.IC.portfolio_results['deaths']['model_central'] /
                      pps.IC.portfolio_results['population']['model_central'],
            'IC_LB_inc': pps.IC.portfolio_results['deaths']['model_low'] /
                         pps.IC.portfolio_results['population']['model_central'],
            'IC_UB_inc': pps.IC.portfolio_results['deaths']['model_high'] /
                         pps.IC.portfolio_results['population']['model_central'],
            'IC_LB_adj': (pps.IC.portfolio_results['deaths']['model_low'])*0.9,
            'IC_UB_adj': (pps.IC.portfolio_results['deaths']['model_high'])*1.1,
        }
    )

    # Save df
    tbh_deaths.to_csv(path_to_sessions_folder / 'tbh_deaths_2035.csv')

    tb_deaths = pd.DataFrame(
        index=pd.Index(list(range(2010, 2036)), name='Year'),
        data={
            'Actual': pps.PARTNER['deathshivneg'],
            'GP': pps.CF_forgraphs['deathshivneg'],
            'Counterfactual': pps.CF_InfAve.portfolio_results['deathshivneg']['model_central'],
            'IC': pps.IC.portfolio_results['deathshivneg']['model_central'],
            'IC_LB': pps.IC.portfolio_results['deathshivneg']['model_low'],
            'IC_UB': pps.IC.portfolio_results['deathshivneg']['model_high'],
            'pop_actual': pps.PARTNER['population'],
            'pop_cf': pps.CF_InfAve.portfolio_results['population']['model_central'],
            'pop_ic': pps.IC.portfolio_results['population']['model_central'],
            'Actual_inc': pps.PARTNER['deathshivneg'] / pps.PARTNER["population"],
            'GP_inc': pps.CF_forgraphs['mortalityhivneg'],
            'CF_inc': pps.CF_InfAve.portfolio_results['deathshivneg']['model_central'] /
                      pps.CF_InfAve.portfolio_results['population']['model_central'],
            'IC_inc': pps.IC.portfolio_results['deathshivneg']['model_central'] /
                      pps.IC.portfolio_results['population']['model_central'],
            'IC_LB_inc': pps.IC.portfolio_results['deathshivneg']['model_low'] /
                         pps.IC.portfolio_results['population']['model_central'],
            'IC_UB_inc': pps.IC.portfolio_results['deathshivneg']['model_high'] /
                         pps.IC.portfolio_results['population']['model_central'],
            'IC_LB_adj': (pps.IC.portfolio_results['deathshivneg']['model_low'])*0.9,
            'IC_UB_adj': (pps.IC.portfolio_results['deathshivneg']['model_high'])*1.1,
        }
    )

    # Save df
    tb_deaths.to_csv(path_to_sessions_folder / 'tb_deaths_2035.csv')

