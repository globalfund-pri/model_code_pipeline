"""Do the analysis for all three diseases and produce the report"""

from scripts.ic7.hiv.hiv_analysis import get_hiv_analysis
from scripts.ic7.malaria.malaria_analysis import get_malaria_analysis
from scripts.ic7.tb.tb_analysis import get_tb_analysis
from tgftools.analysis import Analysis
from tgftools.report import Report
from scripts.ic7.shared.htm_report import HTMReport, SetOfPortfolioProjections
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

    analysis.set_innvation_on()
    analysis.set_handle_out_of_bounds()
    analysis.set_tgf_funding(file)
    analysis.set_non_tgf_funding(file)
    analsysi.set_scenario_desciptor(file)

    approach = 'b'

    return SetOfPortfolioProjections(
        IC=analysis.portfolio_projection_approach_b(
            # methods = ['local_start_at_random'],
            # methods=None,
            methods=['ga_backwards', 'ga_forwards', ],
            optimisation_params={
                'years_for_obj_func': analysis.parameters.get('YEARS_FOR_OBJ_FUNC'),
                'force_monotonic_decreasing': True,
            },
        ) if approach == 'b' else analysis.portfolio_projection_approach_a(),
        CF_InfAve=analysis.portfolio_projection_counterfactual('CC_CC'),
        CF_LivesSaved=analysis.portfolio_projection_counterfactual('NULL_NULL'),
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


report = HTMReport(
    hiv=get_set_of_portfolio_projections(get_hiv_analysis()),
    tb=get_set_of_portfolio_projections(get_tb_analysis()),
    malaria=get_set_of_portfolio_projections(get_malaria_analysis()),
)


# Generate report
filename = get_root_path() / 'outputs' / 'final_report.xlsx'
report.report(filename)
open_file(filename)
