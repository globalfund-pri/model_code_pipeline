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
This script performs the analysis of the hiv model data. 

This script has the following information and generated the following: 

It sets the following options: 
- To load the raw model data (see LOAD_DATA_FROM_RAW_FILES). This option load the raw model data, cleans it in the 
  disease specific filehandler and put the data in a specific dataframe and performs basic checks. If you running this 
  script for the first time, this option needs to be set to "True" for the code to run. After that it can be set to 
  "False" to increase speed. NOTE: if any changes are made to i) the filehandlers (core filehandler or 
  disease specific filehandler) or ii) to the model data or list of countries, the data needs to be reloaded in order 
  to be reflected. 
- To run the checks (see DO_CHECKS). NOTE: Given the format of the model data, the funding fractions had to be coded up
  differently for the checks compared to the analysis. As such it is recommended that checks are run from the disease 
  specific checks, e.g. hiv_checks.py. More information on how to run the checks can be found there. To perform the 
  analysis and and to account for the above point on funding fractions go to each disease-specific filehandler
  and ensure that in the class e.g. ModelResultsHiv(HIVMixin, ModelResults) the checks are set to 0. There should be two 
  instances in hiv, one in tb and none in malaria. You can search for "check = ".  
- It saves the output of the Approach B to csv. This is done in # Portfolio Projection Approach B: save the optimal 
  allocation of TGF
  
All parameters and files defining this analysis are set out in the following two files: 
- The parameters.toml file, which outlines all the key parameters outlining the analysis, list of scenarios and how they 
  are mapped compared to cc, null and gp, the list of modelled and portfolio countries to run as well as the list of the 
  variables and how these should be handled (scaled to portfolio or not).
- The filepaths.toml, which outlines which model data and funding data to be used for this analysis.  

NOTE: Scenarios for the various counterfactuals are set in the script "Main_results_for_investment_case.py" under src/
scripts/ic8/analyses. 
"""


def get_hiv_database() -> Database:
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
    """Returns the analysis for HIV."""

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