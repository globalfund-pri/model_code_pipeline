from pathlib import Path

import pandas as pd

from scripts.ic8.shared.create_frontier import filter_for_frontier
from scripts.ic8.tb.tb_checks import DatabaseChecksTb
from scripts.ic8.tb.tb_filehandlers import PartnerDataTb, PFInputDataTb, ModelResultsTb, GpTb
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


def get_tb_database(load_data_from_raw_files: bool = True) -> Database:
    path_to_data_folder = get_data_path()
    project_root = get_root_path()

    # Declare the parameters, indicators and scenarios
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")

    if load_data_from_raw_files:
        # Load the files
        model_results = ModelResultsTb(
            path_to_data_folder / "IC8/modelling_outputs/tb/2024_10_15",
            parameters=parameters,
        )
        # Save the model_results object
        save_var(model_results, project_root / "sessions" / "tb_model_data_ic8.pkl")
    else:
        # Load the model results
        model_results = load_var(project_root / "sessions" / "tb_model_data_ic8.pkl")

    # Load the files
    pf_input_data = PFInputDataTb(
        path_to_data_folder / "IC8/pf/tb/2024_03_28",
        parameters=parameters
    )

    partner_data = PartnerDataTb(
        path_to_data_folder / "IC8/partner/tb/2024_10_17",
        parameters=parameters,
    )

    fixed_gp = FixedGp(
        get_root_path() / "src" / "scripts" / "ic8" / "shared" / "fixed_gps" / "tb_gp.csv",
        parameters=parameters,
    )

    gp = GpTb(
        fixed_gp=fixed_gp,
        model_results=model_results,
        partner_data=partner_data,
        parameters=parameters,
    )

    # Create and return the database
    return Database(
        # These model results take the full cost impact curve as is
        # model_results=model_results,
        # These model results are limited to the points of the cost-impact curve that are on the frontier
        model_results=filter_for_frontier(model_results),
        gp=gp,
        pf_input_data=pf_input_data,
        partner_data=partner_data,
    )


def get_tb_analysis(
        load_data_from_raw_files: bool = True,
        do_checks: bool = False,
) -> Analysis:
    """Return the Analysis object for TB."""

    path_to_data_folder = get_data_path()
    project_root = get_root_path()

    # Declare the parameters, indicators and scenarios
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")

    db = get_tb_database(load_data_from_raw_files=load_data_from_raw_files)

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
    tgf_funding = (
        TgfFunding(
            path_to_data_folder
            / "IC8"
            / "funding"
            / "2024_11_24"
            / "tb"
            / "tgf"
            / "tb_fung_inc_unalc_bs17.csv"
        )
    )

    list = parameters.get_modelled_countries_for('TB')
    tgf_funding.df = tgf_funding.df[tgf_funding.df.index.isin(list)]

    non_tgf_funding = (
        NonTgfFunding(
            path_to_data_folder
            / "IC8"
            / "funding"
            / "2024_11_24"
            / "tb"
            / "non_tgf"
            / "tb_nonfung_base_c.csv"
        )
    )

    non_tgf_funding.df = non_tgf_funding.df[non_tgf_funding.df.index.isin(list)]

    # Change end year
    parameters.int_store['END_YEAR'] = 2035

    return Analysis(
                database=db,
                scenario_descriptor='PF',
                tgf_funding=tgf_funding,
                non_tgf_funding=non_tgf_funding,
                parameters=parameters,
                handle_out_of_bounds_costs=True,
                innovation_on=False,
            )


if __name__ == "__main__":
    LOAD_DATA_FROM_RAW_FILES = False
    DO_CHECKS = False

    # Create the Analysis object
    analysis = get_tb_analysis(
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
    tb_cases.to_csv('tb_cases_2035.csv')

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
    tbh_deaths.to_csv('tbh_deaths_2035.csv')

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
    tb_deaths.to_csv('tb_deaths_2035.csv')

