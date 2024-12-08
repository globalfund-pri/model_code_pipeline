from pathlib import Path

import pandas as pd

from scripts.ic8.shared.create_frontier import filter_for_frontier
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

    # Declare the parameters and filepaths
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    # If load_data_from_raw_files is set to True it will re-load the data else, else use the version saved last loaded
    if load_data_from_raw_files:
        # Load the files
        model_results = ModelResultsTb(
            filepaths.get('tb', 'model-results'),
            parameters=parameters,
        )
        # Save the model_results object
        save_var(model_results, project_root / "sessions" / "tb_model_data_ic8.pkl")
    else:
        # Load the model results
        model_results = load_var(project_root / "sessions" / "tb_model_data_ic8.pkl")

    # Load all other data
    pf_input_data = PFInputDataTb(filepaths.get('tb', 'pf-input-data'), parameters=parameters)
    partner_data = PartnerDataTb(filepaths.get('tb', 'partner-data'), parameters=parameters)
    fixed_gp = FixedGp(filepaths.get('tb', 'gp-data'), parameters=parameters)

    # This calls the code that generates the milestone based GP
    gp = GpTb(
        fixed_gp=fixed_gp,
        model_results=model_results,
        partner_data=partner_data,
        parameters=parameters,
    )

    # Create and return the database
    return Database(
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

    # Declare the parameters and filepaths
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    db = get_tb_database(load_data_from_raw_files=load_data_from_raw_files)

    # Run the checks, if do_checks is set to True
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
    non_tgf_funding = NonTgfFunding(filepaths.get('tb', 'non-tgf-funding'))

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
    analysis = get_tb_analysis(
        load_data_from_raw_files=LOAD_DATA_FROM_RAW_FILES,
        do_checks=DO_CHECKS
    )

    # Make diagnostic report
    analysis.make_diagnostic_report(
        filename=get_root_path() / "outputs" / "diagnostic_report_tb.pdf"
    )

    # Get the finalised Set of Portfolio Projections (decided upon IC scenario and Counterfactual):
    from scripts.ic8.analyses.main_results_for_investment_case import get_set_of_portfolio_projections
    pps = get_set_of_portfolio_projections(analysis)

    # Portfolio Projection Approach B: save the optimal allocation of TGF
    results_from_approach_b = analysis.portfolio_projection_approach_b()

    (
        pd.Series(results_from_approach_b.tgf_funding_by_country) + pd.Series(
        results_from_approach_b.non_tgf_funding_by_country)
    ).to_csv(
        get_root_path() / 'outputs' / 'tb_tgf_optimal_allocation.csv',
        header=False
    )

