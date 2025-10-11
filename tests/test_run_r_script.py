from tgftools.run_r_script import run_r_script
from tgftools.utils import get_root_path


def test_run_r_script():
    test_script_location = get_root_path()  / 'tests/code_and_data_for_tests/r_script.R'
    run_r_script(test_script_location, 'argument1', 10, 'argument3')