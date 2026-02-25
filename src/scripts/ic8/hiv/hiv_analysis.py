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

"""Performs analysis of HIV model data for investment case projections.

This module contains functions for loading, processing, and analyzing HIV model
data to generate portfolio projections and optimal resource allocations.

Configuration Options:
    - LOAD_DATA_FROM_RAW_FILES: Loads raw model data, cleans it in the
      disease-specific filehandler, and stores it in a dataframe with basic checks.
      Set to True on first run. After that, set to False for speed.
      Note: If changes are made to filehandlers or model data/country lists, data
      must be reloaded.

    - DO_CHECKS: Runs validation checks. Note: Due to model data format, funding
      fractions are coded differently for checks vs. analysis. It is recommended
      to run checks from disease-specific check scripts (e.g., hiv_checks.py).
      To perform analysis, ensure checks are set to 0 in disease-specific
      filehandlers (e.g., ModelResultsHiv(HIVMixin, ModelResults)). There should
      be two instances in HIV, one in TB, and none in malaria. Search for "check = ".

    - Saves Approach B output to CSV: The optimal allocation of TGF funding.

Configuration Files:
    - parameters.toml: Outlines key analysis parameters, scenarios and their
      mapping to CC, NULL, and GP, list of modeled and portfolio countries,
      and variables with their handling (scaled to portfolio or not).
    - filepaths.toml: Specifies which model data and funding data to use.

Note:
    Scenarios for counterfactuals are set in the script
    "Main_results_for_investment_case.py" under src/scripts/ic8/analyses.
"""


def get_hiv_database() -> Database:
    """Loads and returns the HIV database containing model results and supporting data.

    This function loads HIV model results, PF input data, partner data, and GP data,
    assembling them into a Database object. The function can either load from raw
    files or from cached pickle files based on the LOAD_DATA_FROM_RAW_FILES parameter.

    Returns:
        Database: A Database object containing model results, GP projections,
            PF input data, and partner data for HIV.

    Note:
        If LOAD_DATA_FROM_RAW_FILES is True, raw data is loaded and cached.
        If False, previously cached data is loaded for faster processing.
    """
    # Declare the parameters and filepaths
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    load_data_from_raw_files = parameters.get('LOAD_DATA_FROM_RAW_FILES')

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
    pf_input_data = PFInputDataHIV(filepaths.get('hiv', 'pf-input-data'), parameters=parameters)
    partner_data = PartnerDataHIV(filepaths.get('hiv', 'partner-data'), parameters=parameters)
    fixed_gp = FixedGp(filepaths.get('hiv', 'gp-data'), parameters=parameters)

    # This calls the code that generates the milestone based GP, even if we do not have one for HIV
    gp = GpHiv(
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


def get_hiv_analysis() -> Analysis:
    """Creates and returns an Analysis object for HIV with funding assumptions.

    This function loads the HIV database along with TGF and non-TGF funding
    assumptions to create a complete Analysis object ready for portfolio projections
    and optimization.

    Returns:
        Analysis: An Analysis object containing the HIV database, funding assumptions,
            and parameters for investment case analysis.
    """

    # Declare the parameters and filepaths
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    # Load the database
    db = get_hiv_database()

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

    # Create the Analysis object
    analysis = get_hiv_analysis()

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