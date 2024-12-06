from scripts.ic7.tb.tb_analysis import get_tb_database
from tgftools.analysis import Analysis
from tgftools.filehandler import Parameters, TgfFunding, NonTgfFunding
from tgftools.utils import get_root_path, get_data_path

project_root = get_root_path()
path_to_data_folder = get_data_path()
funding_path = path_to_data_folder / "IC7" / 'TimEmulationTool' / "funding"


# Declare the parameters, indicators and scenarios
parameters = Parameters(project_root / "src" / "scripts" / "ic7" / "shared" / "parameters.toml")

tb_db = get_tb_database(load_data_from_raw_files=False)

# Load assumption for budgets for this analysis
tgf_funding = (
    TgfFunding(
        path_to_data_folder
        / "IC7/TimEmulationTool"
        / "funding"
        / "tb"
        / "tgf"
        / "tb_Fubgible_gf_17b_incUnalloc.csv"
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


a_inn_on = Analysis(
        database=tb_db,
        tgf_funding=tgf_funding,
        non_tgf_funding=non_tgf_funding,
        parameters=parameters,
    ).portfolio_projection_approach_a()

a_inn_off = Analysis(
        database=tb_db,
        tgf_funding=tgf_funding,
        non_tgf_funding=non_tgf_funding,
        parameters=parameters,
    ).portfolio_projection_approach_a()
a_inn_off.parameters.int_store["INNOVATION_ON"] = False  # turn innovation off in parameters


df_inn_off = a_inn_off.portfolio_results['cases']
df_inn_on = a_inn_on.portfolio_results['cases']

df_inn_off_d = a_inn_off.portfolio_results['deathshivneg']
df_inn_on_d = a_inn_on.portfolio_results['deathshivneg']


