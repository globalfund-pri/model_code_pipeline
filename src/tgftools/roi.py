from pathlib import Path
from typing import Dict, Optional

from tgftools.run_r_script import run_r_script
from tgftools.utils import get_root_path


class Roi:
    """This class is used to calculate the ROI.

    It works by running the 'R scripts' developed by Prof Stephen Resch, which are stored in `src/tgftools/roi/`.

    The scripts use the following as inputs:
        * a dump-file of the model results for each disease. These can be created by `generate_dump_files_for_ic8()`
        * a parameter file (a default for which is stored at `src/tgftools/roi/parameters.yml`)
        * resource files which are stored at `resource/roi/`.

    The scripts output a csv file at `self.output_file_location`.

    """

    def __init__(self):
        pass

    def generate_dump_files_for_ic8(self):
        """This generates the dump files are stores them in the appropriate location for the ROI analysis. This step
        can be skipped if the dump files are already available."""

        # This helper script is for IC8 specifically
        from scripts.ic8.analyses.main_results_for_investment_case import dump_ic_scenario_to_file
        return dump_ic_scenario_to_file(filename_stub=get_root_path() / 'outputs' / 'dump_ic')  # returns list of filenames

    def run_analysis(
            self,
            dump_file_locations: Dict[str, Path],
            output_filename_stub: Optional[Path] = None,
            parameters_file_location: Optional[Path] = None
    ):
        """This runs the R scripts to calculate the ROI.
        N.B. We expect the dump file location is a dict of the form {disease: dumpfile location, ...}."""

        # Set default output location if none specified
        if output_filename_stub is None:
            output_filename_stub = get_root_path() / 'outputs' / 'roi'

        # Use default parameters file if not specified
        if parameters_file_location is None:
            parameters_file_location = get_root_path() / 'resources' / 'parameters.yml'

        # Script location of the main ROI analysis
        script_location = get_root_path() / 'src' / 'tgftools' / 'roi' / 'main.R'

        # @Stephen - not sure if it's one script for all diseases, or one per disease. Have done it here assuming
        # that we call the R script once per each disease

        for disease in dump_file_locations.keys():
            run_r_script(
                script_location,
                dump_file_locations[disease],
                f"{output_filename_stub}_{disease}.csv",
                parameters_file_location
            )

    def create_resource_files(self):
        """This creates the resource files for the R scripts and stores them in resource/roi/"""
        # @Stephen -- following the code above, here we could point to scripts(s) that ingest the files



if __name__ == "__main__":

    # For testing purposes, this uses the class to do the default analysis.
    r = Roi()
    r.create_resource_files()  # <--- as discussed, we don't need this to be fully automatic
    # filenmaes = r.generate_dump_files_for_ic8()  # <-- generate the files in default locations (filenames are returned)

    dump_file_locations = {
        'hiv': get_root_path() / 'outputs' / 'dump_ic_hiv.csv',
        'tb': get_root_path() / 'outputs' / 'dump_ic_tb.csv',
        'malaria': get_root_path() / 'outputs' / 'dump_ic_malaria.csv',
    }
    r.run_analysis(dump_file_locations=dump_file_locations)

