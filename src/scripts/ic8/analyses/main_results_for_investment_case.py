"""
This script is the one to run if you want to run the full analysis for all three diseases and produce the final
report containing the graphs and key stats. Please read the below carefully before running this script.
"""
from pathlib import Path
from typing import Optional

import pandas as pd

from scripts.ic8.hiv.hiv_analysis import get_hiv_analysis
from scripts.ic8.malaria.malaria_analysis import get_malaria_analysis
from scripts.ic8.tb.tb_analysis import get_tb_analysis
from tgftools.analysis import Analysis
from tgftools.filehandler import Parameters
from tgftools.report import Report
from scripts.ic8.shared.htm_report import HTMReport, SetOfPortfolioProjections
from tgftools.utils import get_root_path, save_var, load_var, open_file

""" This file can be used to run the analyses of the three disease model output and feed them into the report. 

This script has the following information and generated the following: 
- It maps the main scenario and counterfactuals that will be used in the htm_report script. NOTE: be sure to review 
  these and update them as necessary. For example in IC7 the counterfactual name was different than this IC
- It 'dumps' the data needed for other pieces for work, i.e. Nick's work on freed-up capacity and Stephen's work on ROI, 
  and inequality. This part of the script sets the scenarios that need to be 'dumped' and will output all the indicators
  NOTE: be sure to review this and set the correct scenarios that need to be saved, i.e. in IC7 the main scenario was 
  called 'IC_IC', now called 'IC' and make sure all the indicators needed are included in both the disease-specific
  filehandler and defined in the parameter.toml.
- It generated the final report containing the graphs and key stats, saved under the name at the bottom of the script. 

This class holds the following options: 
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
- To run the analysis (see RUN_ANALYSIS). This option runs the analysis itself, i.e. Approach A or B. This option needs
  to be set to "True" for the code to run. After that, this option can be set to "False" to increase running speed. 
  NOTE: if any changes are made to the analysis (e.g. running another scenario, another funding 
  envelope, another non-tgf scenario or new funding data), the analysis needs to be re-run in order to reflect these 
  updates.
- NOTE: if load_data_from_raw_files and run_analysis under dump_projections are set to false it may not update the data 
  being saved for Nick and Stephen and may result in errors. 
  
All parameters and files defining this analysis are set out in the following two files: 
- The parameters.toml file, which outlines all the key parameters outlining the analysis, list of scenarios and how they 
  are mapped compared to cc, null and gp, the list of modelled and portfolio countries to run as well as the list of the 
  variables and how these should be handled (scaled to portfolio or not).
- The filepaths.toml, which outlines which model data and funding data to be used for this analysis.  

The final report containing the key stats and key graphs are saved under the name set at the bottom of this script.  
"""


def get_set_of_portfolio_projections(analysis: Analysis) -> SetOfPortfolioProjections:
    """Returns set of portfolio projections, including the decided configuration for the Investment Case and
    Counterfactual projections,"""
    return SetOfPortfolioProjections(
        IC=analysis.portfolio_projection_approach_b(),
        CF_InfAve=analysis.portfolio_projection_counterfactual('CC_2022'),
        CF_LivesSaved=analysis.portfolio_projection_counterfactual('NULL_2022'),
        CF_LivesSaved_Malaria=analysis.get_counterfactual_lives_saved_malaria(),
        CF_InfectionsAverted_Malaria=analysis.get_counterfactual_infections_averted_malaria(),
        PARTNER=analysis.get_partner(),
        CF_forgraphs=analysis.get_gp(),
        Info={
            "Years of funding: ": str(analysis.years_for_funding),
            "Main scenario name: ": analysis.scenario_descriptor,
            "Adjustment for innovation was applied:": analysis.innovation_on,
            "Did we handle out of bounds costs: ": analysis.handle_out_of_bounds_costs,
            "Which approach do we use: ": 'b',
            "Files used for PF data: ": str(analysis.database.pf_input_data.path),
            "Files used for partner data: ": str(analysis.database.partner_data.path),
            "Files used for model output: ": str(analysis.database.model_results.path),
            "Assumptions for non-GF funding: ": str(analysis.non_tgf_funding.path),
            "Assumptions for TGF funding: ": str(analysis.tgf_funding.path),
        }
    )


def get_report(
        load_data_from_raw_files: bool = True,
        run_analysis: bool = True,
        do_checks: bool = False,
) -> Report:
    project_root = get_root_path()

    if run_analysis:

        # Run the analyses
        hiv_projections = get_set_of_portfolio_projections(
            get_hiv_analysis(
                load_data_from_raw_files=load_data_from_raw_files,
                do_checks=do_checks
            )
        )

        save_var(hiv_projections, project_root / "sessions" / "hiv_analysis_ic8.pkl")

        tb_projections = get_set_of_portfolio_projections(
            get_tb_analysis(
                load_data_from_raw_files=load_data_from_raw_files,
                do_checks=do_checks
            )
        )
        save_var(tb_projections, project_root / "sessions" / "tb_analysis_ic8.pkl")

        malaria_projections = get_set_of_portfolio_projections(
            get_malaria_analysis(
                load_data_from_raw_files=load_data_from_raw_files,
                do_checks=do_checks
            )
        )
        save_var(malaria_projections, project_root / "sessions" / "malaria_analysis_ic8.pkl")

    else:
        # Load the results of the analyses stored
        hiv_projections = load_var(project_root / "sessions" / "hiv_analysis_ic8.pkl")
        tb_projections = load_var(project_root / "sessions" / "tb_analysis_ic8.pkl")
        malaria_projections = load_var(project_root / "sessions" / "malaria_analysis_ic8.pkl")

    report = HTMReport(
        hiv=hiv_projections,
        tb=tb_projections,
        malaria=malaria_projections,
        parameters=Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    )

    return report


def dump_projection_to_file(proj, filename):
    """Write the contents of this projection to a csv file."""
    list_of_dfs = list()  # list of mini dataframes for each indicator for each country

    # Make a list of scenarios that should be saved
    for scenario_descriptor, country_results in zip(
        ['IC', 'CC_2022', 'NULL_2022', ],
        [proj.IC.country_results, proj.CF_InfAve.country_results, proj.CF_LivesSaved.country_results, ]
    ):
        for country in country_results.keys():
            y = country_results[country].model_projection
            indicators = y.keys()
            years = range(2022, 2031)
            for indicator in indicators:
                df = y[indicator][['model_central', 'model_high', 'model_low']].loc[years].reset_index()
                df['indicator'] = indicator
                df['country'] = country
                df['scenario_descriptor'] = scenario_descriptor
                list_of_dfs.append(df)

        # Build a whole df for export
        whole_df = pd.concat(list_of_dfs, axis=0)

        # save the df to csv
        whole_df.to_csv(filename, index=False)


def dump_ic_scenario_to_file(
        load_data_from_raw_files: bool = True,
        run_analysis: bool = True,
        filename_stub: Optional[Path] = None,
) -> None:
    project_root = get_root_path()

    if filename_stub is None:
        print('We need a filename!!')
        return

    if run_analysis:
        # Run the analyses
        hiv_projections = get_set_of_portfolio_projections(
            get_hiv_analysis(
                load_data_from_raw_files=load_data_from_raw_files,
                do_checks=False,
            )
        )
        save_var(hiv_projections, project_root / "sessions" / "hiv_analysis_ic8.pkl")

        tb_projections = get_set_of_portfolio_projections(
            get_tb_analysis(
                load_data_from_raw_files=load_data_from_raw_files,
                do_checks=False,
            )
        )
        save_var(tb_projections, project_root / "sessions" / "tb_analysis_ic8.pkl")

        malaria_projections = get_set_of_portfolio_projections(
            get_malaria_analysis(
                load_data_from_raw_files=load_data_from_raw_files,
                do_checks=False,
            )
        )
        save_var(malaria_projections, project_root / "sessions" / "malaria_analysis_ic8.pkl")

    else:
        # Load the projections
        hiv_projections = load_var(project_root / "sessions" / "hiv_analysis_ic8.pkl")
        tb_projections = load_var(project_root / "sessions" / "tb_analysis_ic8.pkl")
        malaria_projections = load_var(project_root / "sessions" / "malaria_analysis_ic8.pkl")

    # Dump to file
    for (disease, proj) in zip(
            ('hiv', 'tb', 'malaria'),
            (hiv_projections, tb_projections, malaria_projections)
    ):
        dump_projection_to_file(proj=proj, filename=f"{filename_stub}_{disease}.csv")


if __name__ == "__main__":

    outputpath = get_root_path() / 'outputs'

    # This will dump the data to csv for Nick and Stephen
    dump_ic_scenario_to_file(
        load_data_from_raw_files=False,
        run_analysis=True,
        filename_stub=Path(str(outputpath) + "/dump_ic")
    )

    # This is the entry point for running Reports for the HIV, TB and MALARIA combined.
    LOAD_DATA_FROM_RAW_FILES = False
    DO_CHECKS = False
    RUN_ANALYSIS = True

    r = get_report(
        load_data_from_raw_files=LOAD_DATA_FROM_RAW_FILES,
        do_checks=DO_CHECKS,
        run_analysis=RUN_ANALYSIS,
    )

    # Generate report
    filename = get_root_path() / 'outputs' / 'final_report_ic8.xlsx'
    r.report(filename)
    open_file(filename)
