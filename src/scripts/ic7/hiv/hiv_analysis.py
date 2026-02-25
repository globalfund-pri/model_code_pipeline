from scripts.ic7.hiv.hiv_checks import DatabaseChecksHiv
from scripts.ic7.hiv.hiv_filehandlers import PFInputDataHIV, PartnerDataHIV, GpHiv, ModelResultsHiv
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

"""HIV analysis module for processing model output.

This module handles the end-to-end processing of HIV model output, including:

- Loading and managing model results, partner data, and PF input data
- Creating the HIV database with appropriate data sources
- Setting up analysis with funding assumptions
- Configuring scenarios for investment case and counterfactuals

Configuration:
    The module uses parameters from parameters.toml including:
    - LOAD_DATA_FROM_RAW_FILES: Controls whether to reload raw model output
    - File locations for model output, partner data, PF data, and GP parameters
    - TGF and non-TGF funding amounts (including unallocated funds)
    - Investment case scenario selection

Note:
    Scenarios for counterfactuals are set in the HTM class and analysis class.
    Updates to filehandler logic require setting LOAD_DATA_FROM_RAW_FILES to True.
"""


def get_hiv_database() -> Database:
    """Create and return the HIV database with all required data sources.

    Returns:
        Database object containing HIV model results, GP, PF input data,
        and partner data.
    """

    path_to_data_folder = get_data_path()
    project_root = get_root_path()

    # Declare the parameters, indicators and scenarios
    parameters = Parameters(project_root / "src" / "scripts" / "ic7" / "shared" / "parameters.toml")
    load_data_from_raw_files = parameters.get('LOAD_DATA_FROM_RAW_FILES')

    if load_data_from_raw_files:
        # Load the files
        model_results = ModelResultsHiv(
            path_to_data_folder / "IC7/TimEmulationTool/modelling_outputs/hiv",
            parameters=parameters,
        )
        # Save the model_results object
        save_var(model_results, project_root / "sessions" / "hiv_model_results.pkl")

    else:
        # Load the model results
        model_results = load_var(project_root / "sessions" / "hiv_model_results.pkl")

    # Load the files
    pf_input_data = PFInputDataHIV(
        path_to_data_folder / "IC7/TimEmulationTool/pf/hiv",
        parameters=parameters,
    )

    partner_data = PartnerDataHIV(
        path_to_data_folder / "IC7/TimEmulationTool/partner/hiv",
        parameters=parameters,
    )

    fixed_gp = FixedGp(
        get_root_path() / "src" / "scripts" / "IC7" / "shared" / "fixed_gps" / "hiv_gp.csv",
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


def get_hiv_analysis() -> Analysis:
    """Create and return the HIV analysis with funding assumptions.

    Returns:
        Analysis object configured with HIV database, TGF funding,
        non-TGF funding, and parameters.
    """

    path_to_data_folder = get_data_path()
    project_root = get_root_path()

    # Declare the parameters, indicators and scenarios
    parameters = Parameters(project_root / "src" / "scripts" / "ic7" / "shared" / "parameters.toml")

    # Load the database
    db = get_hiv_database()

    # Load assumption for budgets for this analysis
    tgf_funding = (
        TgfFunding(
            path_to_data_folder
            / "IC7/TimEmulationTool"
            / "funding"
            / "hiv"
            / "tgf"
            / "hiv_Fubgible_gf_17b_incUnalloc.csv"
        )
    )
    non_tgf_funding = (
        NonTgfFunding(
            path_to_data_folder
            / "IC7/TimEmulationTool"
            / "funding"
            / "hiv"
            / "non_tgf"
            / "hiv_nonFubgible_dipiBase.csv"
        )
    )

    return Analysis(
        database=db,
        tgf_funding=tgf_funding,
        non_tgf_funding=non_tgf_funding,
        parameters=parameters,
    )


if __name__ == "__main__":

    # Create the Analysis object
    analysis = get_hiv_analysis()

    # To examine results from approach A / B....
    # analysis.portfolio_projection_approach_a()
    # analysis.portfolio_projection_approach_b()
    # analysis.portfolio_projection_counterfactual('CC_CC')

    # Get the finalised Set of Portfolio Projections (decided upon IC scenario and Counterfactual):
    from scripts.ic7.analyses.main_results_for_investment_case import get_set_of_portfolio_projections
    pps = get_set_of_portfolio_projections(analysis)
