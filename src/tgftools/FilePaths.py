"""File path handler for TGF tools analysis.

This module provides the FilePaths class for managing file paths from TOML
configuration files.
"""
import tomllib
from pathlib import Path
from typing import Literal

from tgftools.utils import get_data_path


class FilePaths:
    """File path handler that loads and manages file paths from TOML configuration.

    This class reads a TOML configuration file and provides convenient access
    to disease-specific file paths.

    Attributes:
        int_store: Dictionary containing the loaded TOML configuration.
        path_to_data_folder: Path to the data folder obtained from utils.
    """

    def __init__(self, path: Path):
        """Initialize the FilePaths handler.

        Args:
            path: Path to the TOML configuration file.
        """
        # Load the parameters file using tomllib library
        with open(path, 'rb') as f:
            self.int_store: dict = tomllib.load(f)
        self.path_to_data_folder = get_data_path()

    def get(self, disease: Literal['hiv', 'tb', 'malaria'], what: str) -> Path:
        """Get the file path for a specific disease and file type.

        Args:
            disease: The disease identifier ('hiv', 'tb', or 'malaria').
            what: The file type identifier to retrieve from the configuration.

        Returns:
            Complete path to the requested file, combining the data folder path
            with the configured relative path.
        """
        return Path(self.path_to_data_folder / self.int_store.get(disease.upper()).get(what.upper()))



