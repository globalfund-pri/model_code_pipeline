from pathlib import Path

import pandas as pd

from scripts.ic8.hiv.hiv_checks import DatabaseChecksHiv
from scripts.ic8.hiv.hiv_filehandlers import ModelResultsHiv, PFInputDataHIV, PartnerDataHIV, GpHiv
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
    get_root_path,
    load_var,
    save_var,
)

"""
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


def get_hiv_database(load_data_from_raw_files: bool = True) -> Database:

    # Declare the parameters and filepaths
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    # If load_data_from_raw_files is set to True it will re-load the data else, else use the version saved last loaded
    if load_data_from_raw_files:
        # Load the files
        model_results = ModelResultsHiv(filepaths.get('hiv', 'model-results'), parameters=parameters)
        # Save the model_results object
        save_var(model_results, project_root / "sessions" / "hiv_model_data_ic8.pkl")

    else:
        # Load the model results
        model_results = load_var(project_root / "sessions" / "hiv_model_data_ic8.pkl")

    # Load all other data
    pf_input_data = PFInputDataHIV(filepaths.get('hiv', 'pf-input-data'),parameters=parameters)
    partner_data = PartnerDataHIV(filepaths.get('hiv', 'partner-data'), parameters=parameters)
    fixed_gp = FixedGp(filepaths.get('hiv', 'gp-data'), parameters=parameters)

    # This calls the code that generates the milestone based GP, even if we do not have one for HIV
    gp = GpHiv(
        fixed_gp=fixed_gp,
        model_results=model_results,
        partner_data=partner_data,
        parameters=parameters
    )

    # Create and return the database
    return Database(
        model_results=model_results,
        gp=gp,
        pf_input_data=pf_input_data,
        partner_data=partner_data,
    )


def get_hiv_analysis(
        load_data_from_raw_files: bool = True,
        do_checks: bool = False,
) -> Analysis:
    """Returns the analysis for HIV."""

    # Declare the parameters and filepaths)
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    # Load the database
    db = get_hiv_database(load_data_from_raw_files=load_data_from_raw_files)

    # Run the checks, if do_checks is set to True
    if do_checks:
        DatabaseChecksHiv(
            db=db,
            parameters=parameters,
        ).run(
            suppress_error=True,
            filename=project_root / "outputs" / "hiv_last_report.pdf"
        )

    # Load assumption for budgets for this analysis
    tgf_funding = TgfFunding(filepaths.get('hiv', 'tgf-funding'))
    non_tgf_funding = NonTgfFunding(filepaths.get('hiv', 'non-tgf-funding'))

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
    analysis = get_hiv_analysis(
        load_data_from_raw_files=LOAD_DATA_FROM_RAW_FILES,
        do_checks=DO_CHECKS
    )

    # Make diagnostic report
    analysis.make_diagnostic_report(
        filename=get_root_path() / "outputs" / "diagnostic_report_hiv.pdf"
    )

    # Get the finalised Set of Portfolio Projections (decided upon IC scenario and Counterfactual):
    from scripts.ic8.analyses.main_results_for_investment_case import get_set_of_portfolio_projections
    pps = get_set_of_portfolio_projections(analysis)

    # Portfolio Projection Approach B: save the optimal allocation of TGF
    results_from_approach_b = analysis.portfolio_projection_approach_b()

    (
        pd.Series(results_from_approach_b.tgf_funding_by_country) + pd.Series(results_from_approach_b.non_tgf_funding_by_country)
    ).to_csv(
        get_root_path() / 'outputs' / 'hiv_tgf_optimal_allocation.csv',
        header=False
    )

    list_of_dfs = list()  # list of mini dataframes for each indicator for each country

    for country in pps.IC.country_results.keys():
        y = pps.IC.country_results[country].model_projection
        indicators = ['cases', 'deaths']
        years = range(2022, 2031)
        for indicator in indicators:
            df = y[indicator][['model_central', 'model_high', 'model_low']].loc[years].reset_index()
            df['indicator'] = indicator
            df['country'] = country
            df['scenario_descriptor'] = "PF"
            list_of_dfs.append(df)

    # build whole df for export
    whole_df = pd.concat(list_of_dfs, axis=0)

    # save to csv
    whole_df.to_csv("hiv_results_17bn_2.csv", index=False)

