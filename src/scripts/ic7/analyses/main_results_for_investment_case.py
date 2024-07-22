"""Do the analysis for all three diseases and produce the report"""

from scripts.ic7.hiv.hiv_filehandlers import PartnerDataHIV, PFInputDataHIV, ModelResultsHiv, GpHiv
from scripts.ic7.malaria.malaria_filehandlers import ModelResultsMalaria, PFInputDataMalaria, PartnerDataMalaria
from scripts.ic7.tb.tb_filehandlers import PFInputDataTb, PartnerDataTb
from tgftools.analysis import Analysis
from tgftools.database import Database
from tgftools.filehandler import NonTgfFunding, TgfFunding, Parameters, FixedGp
from scripts.ic7.shared.htm_report import HTMReport, SetOfPortfolioProjections
from tgftools.utils import get_root_path, open_file



def generate_projections(
    database,
    tgf_funding,
    non_tgf_funding,
    parameters,
) -> SetOfPortfolioProjections:
    """Returns set of portfolio projections, including the decided configuration for the Investment Case and
    Counterfactual projections. As the projections for all diseases and created by this function, the specification
    of the projection is the same for all diseases. This is *the* place where all decisions about the construction
    of the forward projections are declared."""

    # Create Analysis
    analysis = Analysis(
        database=database,
        scenario_descriptor='IC_IC',       # <---- decision about the scenario being used
        tgf_funding=tgf_funding,
        non_tgf_funding=non_tgf_funding,
        parameters=parameters,
        handle_out_of_bounds_costs=True,   # <---- decisions about the construction of the projection
        innovation_on=True,                # <---- decisions about the construction of the projection
    )


    approach = 'b' # <--- The apporach used to create the 'Investment Case' scenario:

    return SetOfPortfolioProjections(
        IC=analysis.portfolio_projection_approach_b(
            methods=['ga_backwards', 'ga_forwards', ],
            optimisation_params={
                'years_for_obj_func': parameters.get('YEARS_FOR_OBJ_FUNC'),
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


class ModelResultsTb:
    pass


if __name__ == '__main__':

    path_to_data_folder = get_root_path()
    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic7" / "shared" / "parameters.toml")

    report = HTMReport(
        hiv=generate_projections(
            database=Database(
                model_results=ModelResultsHiv(
                    path_to_data_folder / "IC7/TimEmulationTool/modelling_outputs/hiv",
                    parameters=parameters),
                gp=GpHiv(
                    fixed_gp=FixedGp(
                        get_root_path() / "src" / "scripts" / "IC7" / "shared" / "fixed_gps" / "hiv_gp.csv",
                        parameters=parameters),
                    model_results=model_results,
                    partner_data=partner_data,
                    parameters=parameters
                ),
                pf_input_data=PFInputDataHIV(
                    path_to_data_folder / "IC7/TimEmulationTool/pf/hiv",
                    parameters=parameters,
                ),
                partner_data=PartnerDataHIV(
                    path_to_data_folder / "IC7/TimEmulationTool/partner/hiv",
                    parameters=parameters,
                ),
            ),
            tgf_funding=TgfFunding(
                path_to_data_folder
                / "IC7/TimEmulationTool"
                / "funding"
                / "hiv"
                / "tgf"
                / "hiv_Fubgible_gf_17b_incUnalloc.csv"),
            non_tgf_funding=NonTgfFunding(
                path_to_data_folder
                / "IC7/TimEmulationTool"
                / "funding"
                / "hiv"
                / "non_tgf"
                / "hiv_nonFubgible_dipiBase.csv"),
        ),
        malaria=generate_projections(
            database=Database(
                model_results=ModelResultsMalaria(
                    path_to_data_folder / "IC7/TimEmulationTool/modelling_outputs/malaria/standard",
                    parameters=parameters
                ),
                gp=gp,
                pf_input_data=PFInputDataMalaria(
                    path_to_data_folder / "IC7/TimEmulationTool/pf/malaria",
                    parameters=parameters
                ),
                partner_data=PartnerDataMalaria(
                    path_to_data_folder / "IC7/TimEmulationTool/partner/malaria",
                    parameters=parameters
                ),
            ),
            tgf_funding=(
                TgfFunding(
                    path_to_data_folder
                    / "IC7/TimEmulationTool"
                    / "funding"
                    / "malaria"
                    / "tgf"
                    / "malaria_Fubgible_gf_17b_incUnalloc.csv"
                )
            ),
            non_tgf_funding=(
                NonTgfFunding(
                    path_to_data_folder
                    / "IC7/TimEmulationTool"
                    / "funding"
                    / "malaria"
                    / "non_tgf"
                    / "malaria_nonFubgible_dipiBase.csv"
                )
            )
        ),
        tb=generate_projections(
            database=Database(
                model_results=ModelResultsTb(
                    path_to_data_folder / "IC7/TimEmulationTool/modelling_outputs/tb",
                    parameters=parameters),
                gp=gp,
                pf_input_data=PFInputDataTb(
                    path_to_data_folder / "IC7/TimEmulationTool/pf/tb",
                    parameters=parameters),
                partner_data= PartnerDataTb(
                    path_to_data_folder / "IC7/TimEmulationTool/partner/tb",
                    parameters=parameters),
            ),
            tgf_funding=(
                TgfFunding(
                    path_to_data_folder
                    / "IC7/TimEmulationTool"
                    / "funding"
                    / "tb"
                    / "tgf"
                    / "tb_Fubgible_gf_17b_incUnalloc.csv"
                )
            ),
            non_tgf_funding=(
                NonTgfFunding(
                    path_to_data_folder
                    / "IC7/TimEmulationTool"
                    / "funding"
                    / "tb"
                    / "non_tgf"
                    / "tb_nonFubgible_dipiBase.csv"
                )
            )
        )
    )


    # Generate report
    filename = project_root / 'outputs' / 'final_report.xlsx'
    report.report(filename)
    open_file(filename)
