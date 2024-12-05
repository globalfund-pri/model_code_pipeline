from pathlib import Path

import pandas as pd

from scripts.ic8.hiv.hiv_checks import DatabaseChecksHiv
from scripts.ic8.hiv.hiv_filehandlers import ModelResultsHiv, PFInputDataHIV, PartnerDataHIV, GpHiv
from scripts.ic8.shared.create_frontier import filter_for_frontier
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

"""This file holds everything relating to processing the model output. 
It contains information on: 
- The location of the parameter file
- The location to the raw model output file and the location the model output should be saved to
- Alternatively, if if the options is set to not reloading the raw data, the location of the file containing the loaded
  model output which has been processed in the filehandler
- The location to pf, partner and gp data and where to save the output of the gp file


It also sets the following options: 
- Whether to load the model output from raw (see LOAD_DATA_FROM_RAW_FILES at the bottom of the file). 
  CAUTION: Updated to the filehandler relating to model output will not be reflected if this option is set to "False". 
- Whether to run checks or not (see DO_CHECKS at the bottom of the file) and, if checks are to be run, where to save the
  report of the checks. 
- Options to set the tgf and non-tgf funding amounts to be used in the analysis. This includes an option to include or 
  exclude unallocated amounts. This information has to be computed outside the MCP (set in the disease-specific analysis 
  scripts when loading the budget assumptions) (see tgf_funding and non_tgf_funding). 
- Which scenario should be used to compute the main investment case scenario (see scenario_descriptor). 

NOTE: Scenarios for the various counterfactuals are set in the HTM class, and disease-specific CFs are set within the
analysis class directly. 

"""


def get_hiv_database(load_data_from_raw_files: bool = True) -> Database:

    # Declare the parameters and filepaths
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    if load_data_from_raw_files:
        # Load the files
        model_results = ModelResultsHiv(filepaths.get('hiv', 'model-results'), parameters=parameters)
        # Save the model_results object
        save_var(model_results, project_root / "sessions" / "hiv_model_data_ic8.pkl")

    else:
        # Load the model results
        model_results = load_var(project_root / "sessions" / "hiv_model_data_ic8.pkl")

    # Load the files
    pf_input_data = PFInputDataHIV(filepaths.get('hiv', 'pf-input-data'),parameters=parameters)
    partner_data = PartnerDataHIV(filepaths.get('hiv', 'partner-data'), parameters=parameters)
    fixed_gp = FixedGp(filepaths.get('hiv', 'gp-data'), parameters=parameters)

    gp = GpHiv(
        fixed_gp=fixed_gp,
        model_results=model_results,
        partner_data=partner_data,
        parameters=parameters
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

    # Run the checks
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
    analysis = get_hiv_analysis(
        load_data_from_raw_files=LOAD_DATA_FROM_RAW_FILES,
        do_checks=DO_CHECKS
    )

    # Make diagnostic report
    analysis.make_diagnostic_report(
        optimisation_params={
                'years_for_obj_func': analysis.parameters.get('YEARS_FOR_OBJ_FUNC'),
                'force_monotonic_decreasing': True,
            }, methods=['ga_backwards', 'ga_forwards', ], provide_best_only=False,
        filename=get_root_path() / "outputs" / "diagnostic_report_hiv.pdf"
    )

    # To examine results from approach A / B....
    # analysis.portfolio_projection_approach_a()
    # analysis.portfolio_projection_approach_b()
    # analysis.portfolio_projection_counterfactual('CC_CC')

    # Get the finalised Set of Portfolio Projections (decided upon IC scenario and Counterfactual):
    from scripts.ic8.analyses.main_results_for_investment_case import get_set_of_portfolio_projections
    pps = get_set_of_portfolio_projections(analysis)

    # Portfolio Projection Approach B: to find optimal allocation of TGF
    results_from_approach_b = analysis.portfolio_projection_approach_b(
        optimisation_params={
            'years_for_obj_func': analysis.parameters.get('YEARS_FOR_OBJ_FUNC'),
            'force_monotonic_decreasing': True,
        }, methods=['ga_backwards', 'ga_forwards', ]
    )

    (
        pd.Series(results_from_approach_b.tgf_funding_by_country) + pd.Series(results_from_approach_b.non_tgf_funding_by_country)
    ).to_csv(
        get_root_path() / 'outputs' / 'hiv_tgf_optimal_allocation.csv',
        header=False
    )

