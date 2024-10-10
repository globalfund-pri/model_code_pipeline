from scripts.ic8.hiv.hiv_checks import DatabaseChecksHiv
from scripts.ic8.hiv.hiv_filehandlers import ModelResultsHiv, PFInputDataHIV, PartnerDataHIV, GpHiv
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

    path_to_data_folder = get_data_path()
    project_root = get_root_path()

    # Declare the parameters, indicators and scenarios
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")

    if load_data_from_raw_files:
        # Load the files
        model_results = ModelResultsHiv(
            path_to_data_folder / "IC8/modelling_outputs/hiv/2024_09_25_v2",
            parameters=parameters,
        )
        # Save the model_results object
        save_var(model_results, project_root / "sessions" / "hiv_model_data_ic8.pkl")

    else:
        # Load the model results
        model_results = load_var(project_root / "sessions" / "hiv_model_data_ic8.pkl")

    # Load the files
    pf_input_data = PFInputDataHIV(
        path_to_data_folder / "IC8/pf/hiv/2024_03_28",
        parameters=parameters,
    )

    partner_data = PartnerDataHIV(
        path_to_data_folder / "IC8/partner/hiv/2024_10_03",
        parameters=parameters,
    )

    fixed_gp = FixedGp(
        get_root_path() / "src" / "scripts" / "IC8" / "shared" / "fixed_gps" / "hiv_gp.csv",
        parameters=parameters,
    )

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
        load_data_from_raw_files: bool = False,
        do_checks: bool = False,
) -> Analysis:
    """Returns the analysis for HIV."""

    path_to_data_folder = get_data_path()
    project_root = get_root_path()

    # Declare the parameters, indicators and scenarios
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")

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
    tgf_funding = (
        TgfFunding(
            path_to_data_folder
            / "IC8"
            / "funding"
            / "2024_10_10"
            / "hiv"
            / "tgf"
            / "hiv_Fungible_gf_17b_incUnalloc.csv"
        )
    )
    non_tgf_funding = (
        NonTgfFunding(
            path_to_data_folder
            / "IC8"
            / "funding"
            / "2024_10_10"
            / "hiv"
            / "non_tgf"
            / "hiv_nonFungible_dipiBase.csv"
        )
    )

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
    LOAD_DATA_FROM_RAW_FILES = True
    DO_CHECKS = False

    # Create the Analysis object
    analysis = get_hiv_analysis(
        load_data_from_raw_files=LOAD_DATA_FROM_RAW_FILES,
        do_checks=DO_CHECKS
    )

    # To examine results from approach A / B....
    # analysis.portfolio_projection_approach_a()
    # analysis.portfolio_projection_approach_b()
    # analysis.portfolio_projection_counterfactual('CC_CC')

    # Get the finalised Set of Portfolio Projections (decided upon IC scenario and Counterfactual):
    from scripts.ic8.analyses.main_results_for_investment_case import get_set_of_portfolio_projections
    pps = get_set_of_portfolio_projections(analysis)
