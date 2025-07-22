"""This script is used to run the report for strategy targets"""
from scripts.ic8.analyses.main_results_for_investment_case import get_set_of_portfolio_projections
from scripts.ic8.hiv.hiv_analysis import get_hiv_analysis
from scripts.ic8.malaria.malaria_analysis import get_malaria_analysis
from scripts.ic8.strategy_targets.st_report import STReport
from scripts.ic8.tb.tb_analysis import get_tb_analysis
from tgftools.filehandler import Parameters
from tgftools.utils import get_root_path, save_var, load_var, open_file


def get_st_report() -> STReport:
    """Returns the report for strategy targets, having re-run/loaded the projections."""

    project_root = get_root_path()
    parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    run_analysis = parameters.get('RUN_ANALYSIS')

    if run_analysis:
        # Run the analyses
        hiv_projections = get_set_of_portfolio_projections(get_hiv_analysis())
        save_var(hiv_projections, project_root / "sessions" / "hiv_analysis_ic8.pkl")

        tb_projections = get_set_of_portfolio_projections(get_tb_analysis())
        save_var(tb_projections, project_root / "sessions" / "tb_analysis_ic8.pkl")

        malaria_projections = get_set_of_portfolio_projections(get_malaria_analysis())
        save_var(malaria_projections, project_root / "sessions" / "malaria_analysis_ic8.pkl")

    else:
        # Load the results of the analyses stored
        hiv_projections = load_var(project_root / "sessions" / "hiv_analysis_ic8.pkl")
        tb_projections = load_var(project_root / "sessions" / "tb_analysis_ic8.pkl")
        malaria_projections = load_var(project_root / "sessions" / "malaria_analysis_ic8.pkl")

    return STReport(
        hiv=hiv_projections,
        tb=tb_projections,
        malaria=malaria_projections,
        parameters=Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")
    )


if __name__ == "__main__":
    # This is the entry point for running the Strategy Report
    outputpath = get_root_path() / 'outputs'

    r = get_st_report()

    # Generate report
    r.report(filename := get_root_path() / 'outputs' / 'strategy_report.xlsx')
    open_file(filename)


