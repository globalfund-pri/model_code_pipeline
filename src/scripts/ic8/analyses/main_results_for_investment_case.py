"""Do the analysis for all three diseases and produce the report"""
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

""" This file holds information relating to running the analysis of the three disease model output and feed them into 
the report class. 

This class holds the following options: 
- to load the raw model data (see LOAD_DATA_FROM_RAW_FILES). These need to be loaded the first time the code is run, but
  can then be set to False to improve speed. NOTE: if any changes are made to the filehandler relating to the model 
  data, the data needs to be reloaded in order to be reflected. 
- to run the checks (see DO_CHECKS)
- to run the analysis (see RUN_ANALYSIS). These need to be run the first time the code is run, but can then be set to 
  False to improve speed. NOTE: if any changes are made to the analysis (e.g. running another scenario, funding 
  envelope, non-tgf scenario or counterfactual, the analysis needs to be re-run in order to be reflected.
- run approach A or B (comment out IC = analysis.portfolio_projection_approach_b to run approach a or 
  IC = analysis.portfolio_projection_approach_a() to run approach B. 
    

The final report containing the key stats and key graphs are saved under the name set at the bottom of this script.  
"""


def get_set_of_portfolio_projections(analysis: Analysis) -> SetOfPortfolioProjections:
    """Returns set of portfolio projections, including the decided configuration for the Investment Case and
    Counterfactual projections,"""
    approach = 'b'
    return SetOfPortfolioProjections(
        IC=analysis.portfolio_projection_approach_b(
            # methods = ['local_start_at_random'],
            # methods=None,
            methods=['ga_backwards', 'ga_forwards', ],
            # methods=["ga_forwards",
            #             "ga_backwards",
            #             "global_start_at_a",
            #             "global_start_at_random",
            #             "local_start_at_a",
            #             "local_start_at_random",],
            optimisation_params={
                'years_for_obj_func': analysis.parameters.get('YEARS_FOR_OBJ_FUNC'),
                'force_monotonic_decreasing': True,
            },
        ) if approach == 'b' else analysis.portfolio_projection_approach_a(),
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
            "Which approach do we use: ": approach,
            "Files used for PF data: ": str(analysis.database.pf_input_data.path),
            "Files used for partner data: ": str(analysis.database.partner_data.path),
            "Files used for model output: ": str(analysis.database.model_results.path),
            "Assumptions for non-GF funding: ": str(analysis.non_tgf_funding.path),
            "Assumptions for TGF funding: ": str(analysis.tgf_funding.path),
        }
    )


def get_report(
        load_data_from_raw_files: bool = False,
        run_analysis: bool = False,
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
        # Load the projections
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

        # build whole df for export
        whole_df = pd.concat(list_of_dfs, axis=0)

        # save to csv
        whole_df.to_csv(filename, index=False)


def dump_ic_scenario_to_file(
        load_data_from_raw_files: bool = False,
        run_analysis: bool = False,
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

    dump_ic_scenario_to_file(
        load_data_from_raw_files=False,
        run_analysis=False,
        filename_stub=Path(str(outputpath) + "/dump_ic")
    )

    # This is the entry point for running Reports for the HIV, TB and MALARIA combined.
    LOAD_DATA_FROM_RAW_FILES = True
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
