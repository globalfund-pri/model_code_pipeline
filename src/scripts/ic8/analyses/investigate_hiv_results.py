from scripts.ic8.hiv.hiv_analysis import get_hiv_analysis
from tgftools.utils import get_root_path

root = get_root_path()

hiv_analysis = get_hiv_analysis(
    load_data_from_raw_files=True,
    do_checks=False
)

methods = ['ga_backwards']

optimisation_params={
    'years_for_obj_func': hiv_analysis.parameters.get('YEARS_FOR_OBJ_FUNC'),
    'force_monotonic_decreasing': True,
}

hiv_analysis.make_diagnostic_report(
    methods=methods,
    optimisation_params=optimisation_params,
    provide_best_only=False,
    filename=root / 'outputs' / 'hiv_diagnostic_report.pdf'
)

