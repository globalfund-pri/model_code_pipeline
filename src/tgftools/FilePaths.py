"""Solution for FilePaths"""
import tomllib
from pathlib import Path
from typing import Literal

from tgftools.utils import get_data_path


class FilePaths:
    """FileHandler that holds parameters for the analysis."""

    def __init__(self, path: Path):
        # Load the parameters file using tomllib library
        with open(path, 'rb') as f:
            self.int_store: dict = tomllib.load(f)
        self.path_to_data_folder = get_data_path()

    def get(self, disease: Literal['hiv', 'tb', 'malaria'], what: str) -> Path:
        """Pass through to `get` of the internally stored dict."""
        return Path(self.path_to_data_folder / self.int_store.get(disease.upper()).get(what.upper()))



