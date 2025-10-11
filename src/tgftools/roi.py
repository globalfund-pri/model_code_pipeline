from tgftools.utils import get_root_path


class Roi:
    """This class is used to calculate the ROI.

    It works by running the 'R scripts' developed by Prof Stephen Resch. They are stored in `src/tgftools/roi/`.

    The scripts use the following as inputs:
        * a dump-file of the model results for each disease: which are stored at `sessions/{disease}_dump_file.xlsx`
            where {disease} includes 'hiv', 'tb' and 'malaria'
        * a parameter file which is stored at `src/tgftools/roi/parameters.yml`
        * resource files which are stored at `resource/roi/`.

    The scripts output a csv file at `sessions/roi.xlsx`.

    """

    def __init__(self):
        self.OUTPUT_TARGETFILE = get_root_path() / 'sessions' / "roi.csv"
        pass

    def generate_dump_files(self):
        """This generates the dump files are stores them in the appropriate location for the ROI analysis. This step
        can be skipped if the dump files are already available."""
        pass

    def run_r_scripts(self):
        """This runs the R scripts to calculate the ROI."""

    def create_resource_files(self):
        """This creates the resource files for the R scripts and stores them in resource/roi/"""
        # @Stephen -- following the code above, here we could point to scripts(s) that ingest the files




if __name__ == "__main__":

    # For testing purposes, this uses the class to do the default analysis.
    r = Roi()
    # r.create_resource_files()  # <--- as discussed, we don't need this to be fully automatic
    r.generate_dump_files()
    r.run_r_scripts()

