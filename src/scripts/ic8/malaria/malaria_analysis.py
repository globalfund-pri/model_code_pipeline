from pathlib import Path

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


def get_malaria_database(load_data_from_raw_files: bool = True) -> Analysis:

    # Declare the parameters and filepaths
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

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

    pf_input_data = PFInputDataMalaria(filepaths.get('malaria', 'pf-input-data'), parameters=parameters)
    partner_data = PartnerDataMalaria(filepaths.get('malaria', 'partner-data'), parameters=parameters)
    fixed_gp = FixedGp(filepaths.get('malaria', 'gp-data'), parameters=parameters)

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


def get_malaria_analysis(
        load_data_from_raw_files: bool = True,
        do_checks: bool = False,
) -> Analysis:
    """Return the Analysis object for Malaria."""

    # Declare the parameters and filepaths
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    filepaths = FilePaths(project_root / "src" / "scripts" / "ic8" / "shared" / "filepaths.toml")

    db = get_malaria_database(load_data_from_raw_files=load_data_from_raw_files)

    # Run the checks
    if do_checks:
        DatabaseChecksMalaria(
            db=db,
            parameters=parameters,
        ).run(
            suppress_error=True,
            filename=project_root / "outputs" / "malaria_report_of_checks.pdf",
        )

    # Load assumption for budgets for this analysis
    tgf_funding = TgfFunding(filepaths.get('malaria', 'tgf-funding'))

    list = parameters.get_modelled_countries_for('MALARIA')
    tgf_funding.df = tgf_funding.df[tgf_funding.df.index.isin(list)]

    non_tgf_funding = NonTgfFunding(filepaths.get('malaria', 'non-tgf-funding'))
    non_tgf_funding.df = non_tgf_funding.df[non_tgf_funding.df.index.isin(list)]

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
    analysis = get_malaria_analysis(
        load_data_from_raw_files=LOAD_DATA_FROM_RAW_FILES,
        do_checks=DO_CHECKS
    )

    analysis.make_diagnostic_report(
        optimisation_params={
                'years_for_obj_func': analysis.parameters.get('YEARS_FOR_OBJ_FUNC'),
                'force_monotonic_decreasing': True,
            }, methods=['ga_backwards', 'ga_forwards', ], provide_best_only=False,
        filename=get_root_path() / "outputs" / "diagnostic_report_malaria.pdf"
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
            pd.Series(results_from_approach_b.tgf_funding_by_country) + pd.Series(
        results_from_approach_b.non_tgf_funding_by_country)
    ).to_csv(
        get_root_path() / 'outputs' / 'malaria_tgf_optimal_allocation.csv',
        header=False
    )
