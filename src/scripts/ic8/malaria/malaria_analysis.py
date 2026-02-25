import pandas as pd

from scripts.ic8.malaria.malaria_checks import DatabaseChecksMalaria
from scripts.ic8.malaria.malaria_filehandlers import ModelResultsMalaria, PFInputDataMalaria, PartnerDataMalaria, \
    GpMalaria
from tgftools.FilePaths import FilePaths
from tgftools.analysis import Analysis
from tgftools.database import Database
from tgftools.filehandler import (
    FixedGp,
    NonTgfFunding,
    Parameters,
    TgfFunding, RegionInformation,
)
from tgftools.utils import (
    get_root_path,
    load_var,
    save_var,
)

"""Performs analysis of malaria model data for investment case projections.

This module contains functions for loading, processing, and analyzing malaria
model data to generate portfolio projections and optimal resource allocations.

Configuration Options:
    - LOAD_DATA_FROM_RAW_FILES: Loads raw model data, cleans it in the
      disease-specific filehandler, and stores it in a dataframe with basic checks.
      Set to True on first run. After that, set to False for speed.
      Note: If changes are made to filehandlers or model data/country lists, data
      must be reloaded.

    - DO_CHECKS: Runs validation checks. Note: Although for HIV and TB the new data
      structure means it is not recommended to run checks from this file, for malaria
      it is possible to run checks from this file as funding fractions match the
      expected number of steps and their fractions.

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


def get_malaria_database() -> Database:
    """Loads and returns the malaria database containing model results and supporting data.

    This function loads malaria model results, PF input data, partner data, and GP data,
    assembling them into a Database object. The function can either load from raw
    files or from cached pickle files based on the LOAD_DATA_FROM_RAW_FILES parameter.

    Returns:
        Database: A Database object containing model results, GP projections,
            PF input data, and partner data for malaria.

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
        model_results = ModelResultsMalaria(
            filepaths.get('malaria', 'model-results'),
            parameters=parameters
        )
        # Save the model_results object
        save_var(model_results, project_root / "sessions" / "malaria_model_data_ic8.pkl")
    else:
        # Load the model results
        model_results = load_var(project_root / "sessions" / "malaria_model_data_ic8.pkl")

    # Load all other data
    pf_input_data = PFInputDataMalaria(filepaths.get('malaria', 'pf-input-data'), parameters=parameters)
    partner_data = PartnerDataMalaria(filepaths.get('malaria', 'partner-data'), parameters=parameters)
    fixed_gp = FixedGp(filepaths.get('malaria', 'gp-data'), parameters=parameters)

    # This calls the code that generates the milestone based GP
    gp = GpMalaria(
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

def get_malaria_database_subset(load_data_from_raw_files: bool = True, country_subset_param: str = None) -> Database:
    """Loads and returns a subset of the malaria database filtered by region.

    This function loads malaria model results for a specific subset of countries
    based on regional flags. It filters model results, PF input data, and partner
    data to include only countries in the specified region.

    Args:
        load_data_from_raw_files: If True, loads from raw files. If False, loads
            from cached pickle files. Defaults to True.
        country_subset_param: Regional flag identifier to filter countries. If None,
            uses all countries. Defaults to None.

    Returns:
        Database: A Database object containing filtered model results, GP projections,
            PF input data, and partner data for the specified country subset.
    """
    # Declare the parameters and filepaths
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    # Load the helper class for Regional Information
    region_info = RegionInformation()

    # Define which countries to sum up. This is the place where we would filter for regions if the run requests this
    country_in_region = region_info.get_countries_by_regional_flag(country_subset_param)

    # If load_data_from_raw_files is set to True it will re-load the data else, else use the version saved last loaded
    if load_data_from_raw_files:
        # Load the files
        model_results = ModelResultsMalaria(
            filepaths.get('malaria', 'model-results'),
            parameters=parameters
        )
        # Save the model_results object
        save_var(model_results, project_root / "sessions" / "malaria_model_data_ic8.pkl")
    else:
        # Load the model results
        model_results = load_var(project_root / "sessions" / "malaria_model_data_ic8.pkl")

    # Load all other data
    pf_input_data = PFInputDataMalaria(filepaths.get('malaria', 'pf-input-data'), parameters=parameters)
    partner_data = PartnerDataMalaria(filepaths.get('malaria', 'partner-data'), parameters=parameters)
    fixed_gp = FixedGp(filepaths.get('malaria', 'gp-data'), parameters=parameters)

    # Get the existing countries in the partner_data index
    existing_partner_countries = set(partner_data.df.index.get_level_values('country').unique())
    filtered_partner_countries = [country for country in country_in_region if country in existing_partner_countries]
    existing_pf_countries = set(pf_input_data.df.index.get_level_values('country').unique())
    filtered_pf_countries = [country for country in country_in_region if country in existing_pf_countries]
    existing_model_countries = set(model_results.df.index.get_level_values('country').unique())
    filtered_model_countries = [country for country in country_in_region if country in existing_model_countries]

    # Filter country_list to only include countries present in partner_data
    partner_data.df = partner_data.df.loc[(slice(None), filtered_partner_countries, slice(None), slice(None))]
    pf_input_data.df = pf_input_data.df.loc[(slice(None), filtered_pf_countries, slice(None), slice(None))]
    model_results.df = model_results.df.loc[
        (slice(None), slice(None), filtered_model_countries, slice(None), slice(None))]

    # This calls the code that generates the milestone based GP
    gp = GpMalaria(
        fixed_gp=fixed_gp,
        model_results=model_results,
        partner_data=partner_data,
        parameters=parameters,
        country_list=filtered_partner_countries,
    )

    # Create and return the database
    return Database(
        model_results=model_results,
        gp=gp,
        pf_input_data=pf_input_data,
        partner_data=partner_data,
    )


def get_malaria_analysis() -> Analysis:
    """Creates and returns an Analysis object for malaria with funding assumptions.

    This function loads the malaria database along with TGF and non-TGF funding
    assumptions to create a complete Analysis object ready for portfolio projections
    and optimization.

    Returns:
        Analysis: An Analysis object containing the malaria database, funding assumptions,
            and parameters for investment case analysis.
    """

    # Declare the parameters and filepaths
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    db = get_malaria_database()

    # Load assumption for budgets for this analysis
    tgf_funding = TgfFunding(filepaths.get('malaria', 'tgf-funding'))
    non_tgf_funding = NonTgfFunding(filepaths.get('malaria', 'non-tgf-funding'))

    return Analysis(
        database=db,
        tgf_funding=tgf_funding,
        non_tgf_funding=non_tgf_funding,
        parameters=parameters,
    )


if __name__ == "__main__":

    # Create the Analysis object
    analysis = get_malaria_analysis()

    # Make diagnostic report
    analysis.make_diagnostic_report(
        filename=get_root_path() / "outputs" / "diagnostic_report_malaria.pdf"
    )

    # Get the finalised Set of Portfolio Projections (decided upon IC scenario and Counterfactual):
    from scripts.ic8.analyses.main_results_for_investment_case import get_set_of_portfolio_projections

    pps = get_set_of_portfolio_projections(analysis)

    # Portfolio Projection Approach B: save the optimal allocation of TGF
    results_from_approach_b = analysis.portfolio_projection_approach_b()

    (
        pd.Series(results_from_approach_b.tgf_funding_by_country) + pd.Series(results_from_approach_b.non_tgf_funding_by_country)
    ).to_csv(
        get_root_path() / 'outputs' / 'malaria_tgf_optimal_allocation.csv',
        header=False
    )
