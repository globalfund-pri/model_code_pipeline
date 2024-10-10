from pathlib import Path

from scripts.ic8.hiv.hiv_analysis import get_hiv_analysis
from tgftools.filehandler import Parameters
from tgftools.utils import get_root_path, open_file

analysis = get_hiv_analysis()
project_root = get_root_path()
parameters = Parameters(project_root / "src" / "scripts" / "ic8" / "shared" / "parameters.toml")

approach_b = analysis._approach_b(
    optimisation_params={
        "years_for_obj_func": parameters.get("YEARS_FOR_OBJ_FUNC"),
        "force_monotonic_decreasing": True,
    })
# Inspect the pre-processed model results
results = approach_b.run(methods=["ga_backwards"], provide_best_only=True)

filename = project_root / Path("outputs") / 'inspect_model_results_hiv_9Oct.pdf'
# approach_b.inspect_model_results(plt_show=False, filename=filename)

approach_b.do_report(results=results,filename=filename)
open_file(filename)