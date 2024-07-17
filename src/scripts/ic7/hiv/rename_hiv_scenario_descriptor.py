import re
from typing import Tuple

import numpy as np
import pandas as pd

from tgftools.filehandler import Scenarios
from tgftools.utils import get_data_path


def rename_hiv_scenario_descriptor(original: str) -> Tuple[str, float]:
    """Returns tuple in the form (scenario_descriptor in the standard format, funding_fraction) given the naming
    convention used in the HIV model results. If the name is not one of the scenarios recognised, it is return as NAN.
    """
    # Screen out the special cases:
    if original == "GP_GP":
        return "GP_GP", np.nan
    elif original == "ALWAYS_ZERO_COV":
        return "NULL_NULL", np.nan
    elif original == "ContinuedDisruption_CONSTCOV":
        return "CC_CC", np.nan

    # Use regular expression to interpret the others
    pattern = r"([\w]+) ([\d]{2,3})([\w]+|\Z)"

    if re.search(pattern, original) is not None:
        first_part = re.search(pattern, original).group(1)
        funding_fraction = float(re.search(pattern, original).group(2)) / 100.0
        last_part = re.search(pattern, original).group(3)

        mapping_first_part = {
            "Target_Optimized": "PF",
            "PastPerformance_Optimized": "PP",
            "ContinuedDisruption_Optimized": "CD",
        }

        mapping_last_part = {
            "": "MC",
            "_Target": "GP",
        }

        try:
            return (
                f"{mapping_first_part[first_part]}_{mapping_last_part[last_part]}",
                funding_fraction,
            )
        except KeyError:
            return float("nan"), float("nan")
    else:
        return float("nan"), float("nan")


if __name__ == "__main__":
    # Get scenario names in the original file
    path_to_data_hiv_files = (
        get_data_path() / "IC7/TimEmulationTool/modelling_outputs/hiv"
    )
    one_file = path_to_data_hiv_files / "ETH_HIV_10dec21.xlsx"

    # Get the set of original scenario_descriptors from a model results file
    df = pd.read_excel(one_file)
    originals = set(df["Scenario"].unique())

    # Examples mapping from the original string to a correct tuple
    examples = {
        "GP_GP": ("GP_GP", np.nan),
        "ALWAYS_ZERO_COV": ("NULL_NULL", np.nan),
        "Constant_coverage": ("CC_CC", np.nan),
        "Target_Optimized 20": ("PF_MC", 0.2),
        "Target_Optimized 20_Target": ("PF_GP", 0.2),
        "PastPerformance_Optimized 20": ("PP_MC", 0.2),
        "PastPerformance_Optimized 20_Target": ("PP_GP", 0.2),
        "ContinuedDisruption_Optimized 20": ("CD_MC", 0.2),
        "ContinuedDisruption_Optimized 20_Target": ("CD_GP", 0.2),
    }

    # Check that these examples exhaustively cover all the expected output scenario_descriptors
    scenario_names = Scenarios().names
    assert set(scenario_names) == {eg[0] for eg in examples.values()}

    # Test the renaming function against each example
    for _original, _correct in examples.items():
        rtn = rename_hiv_scenario_descriptor(_original)
        assert _correct == rtn, f"Problem {_original } -> {_correct}, but got {rtn}"

    # Test the renaming function against all the scenario descriptors in the model results file
    collected_scenario_descriptors = set()
    for _original in originals:
        t = rename_hiv_scenario_descriptor(_original)
        if isinstance(t[0], str):
            assert isinstance(t, tuple)
            assert t[0] in scenario_names
            assert isinstance(t[1], float)
            collected_scenario_descriptors.add(t[0])
        else:
            assert _original not in scenario_names

    assert collected_scenario_descriptors == set(
        scenario_names
    ), "not all scenarios captured"
