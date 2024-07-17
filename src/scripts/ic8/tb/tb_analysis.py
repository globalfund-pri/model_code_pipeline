from scripts.ic7.tb.tb_checks import DatabaseChecksTb
from scripts.ic7.tb.tb_filehandlers import PartnerDataTb, PFInputDataTb, GpTb, ModelResultsTb
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


def get_tb_analysis(
        load_data_from_raw_files: bool = True,
        do_checks: bool = False,
) -> Analysis:
    """Return the Analysis object for TB."""

    path_to_data_folder = get_data_path()
    project_root = get_root_path()

    # Declare the parameters, indicators and scenarios
    parameters = Parameters(project_root / "src" / "scripts" / "ic7" / "shared" / "parameters.toml")

    if load_data_from_raw_files:
        # Load the files
        model_results = ModelResultsTb(
            path_to_data_folder / "IC7/TimEmulationTool/modelling_outputs/tb",
            parameters=parameters,
        )
        # Save the model_results object
        save_var(model_results, project_root / "sessions" / "tb_model_data.pkl")
    else:
        # Load the model results
        model_results = load_var(project_root / "sessions" / "tb_model_data.pkl")

    # Load the files
    pf_input_data = PFInputDataTb(
        path_to_data_folder / "IC7/TimEmulationTool/pf/tb",
        parameters=parameters
    )

    partner_data = PartnerDataTb(
        path_to_data_folder / "IC7/TimEmulationTool/partner/tb",
        parameters=parameters,
    )

    fixed_gp = FixedGp(
        get_root_path() / "src" / "scripts" / "ic7" / "shared" / "fixed_gps" / "tb_gp.csv",
        parameters=parameters,
    )

    gp = GpTb(
        fixed_gp=fixed_gp,
        model_results=model_results,
        partner_data=partner_data,
        parameters=parameters,
    )

    gp.save(project_root / "outputs" / "tb_gp.csv")

    # Create the database
    db = Database(
        model_results=model_results,
        gp=gp,
        pf_input_data=pf_input_data,
        partner_data=partner_data,
    )

    # Run the checks
    if do_checks:
        DatabaseChecksTb(
            db=db,
            parameters=parameters
        ).run(
            suppress_error=True,
            filename=project_root / "outputs" / "tb_report_of_checks.pdf"
        )

    # Load assumption for budgets for this analysis
    tgf_funding = (
        TgfFunding(
            path_to_data_folder
            / "IC7/TimEmulationTool"
            / "funding"
            / "tb"
            / "tgf"
            / "tb_Fubgible_gf_11b_incUnalloc.csv"
        )
    )
    non_tgf_funding = (
        NonTgfFunding(
            path_to_data_folder
            / "IC7/TimEmulationTool"
            / "funding"
            / "tb"
            / "non_tgf"
            / "tb_nonFubgible_dipiBase.csv"
        )
    )

    return Analysis(
        database=db,
        scenario_descriptor='IC_IC',
        tgf_funding=tgf_funding,
        non_tgf_funding=non_tgf_funding,
        parameters=parameters,
        handle_out_of_bounds_costs=True,
        innovation_on=True,
    )


if __name__ == "__main__":
    LOAD_DATA_FROM_RAW_FILES = False
    DO_CHECKS = False

    # Create the Analysis object
    analysis = get_tb_analysis(
        load_data_from_raw_files=LOAD_DATA_FROM_RAW_FILES,
        do_checks=DO_CHECKS
    )

