import configparser
import os
import platform
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Union

import dill
import git
import numpy as np

"""Collection of utility functions used across the framework.

This module provides various utility functions for repository management, file operations,
message handling, and platform-specific operations.
"""


def get_root_path(starter_path: Optional[Path] = None) -> Path:
    """Return the absolute path of the repository root.

    Args:
        starter_path: Optional reference location from which to begin search.
            If omitted, the location of this file is used.

    Returns:
        The absolute path to the repository root directory.

    Raises:
        OSError: If the provided starter_path does not exist or is not an absolute path.
    """

    def get_git_root(path: Path) -> Path:
        """Return the path of the git repository root.

        Based on: https://stackoverflow.com/a/41920796

        Args:
            path: Path from which to search for the git repository root.

        Returns:
            The absolute path to the git repository root directory.
        """
        git_repo = git.Repo(path, search_parent_directories=True)
        git_root = git_repo.working_dir
        return Path(git_root)

    if starter_path is None:
        return get_git_root(__file__)
    elif Path(starter_path).exists() and Path(starter_path).is_absolute():
        return get_git_root(starter_path)
    else:
        raise OSError("File Not Found")


def get_commit_revision_number() -> str:
    """Return the commit revision number at the HEAD position in the repository.

    Returns:
        The hexadecimal SHA of the current HEAD commit.
    """
    return str(git.Repo(get_root_path()).head.commit.hexsha)


def read_txt(file: Path) -> List[str]:
    """Read the contents of a text file and return a list of lines.

    Args:
        file: Path to the text file to read.

    Returns:
        A list where each element is a line from the text file with newline characters removed.
    """
    with open(file) as f:
        lines = f.readlines()
    return list(map(lambda s: s.replace("\n", ""), lines))


def get_files_with_extension(path: Path, extension: str) -> List[Path]:
    """Return a list of file paths with a specific extension in a directory.

    Args:
        path: Directory path to search for files.
        extension: File extension to match (without the leading dot).

    Returns:
        A list of Path objects for files matching the specified extension.
    """
    return list(path.glob(f"*.{extension}"))


class Messages:
    """Capture a stream of messages that can be printed to console and written to a file.

    This class collects string messages, optionally prints them to the console,
    and provides functionality to write all collected messages to a text file.

    Attributes:
        print_to_console: Whether to print messages to the console when added.
        list_of_messages: Internal storage of all collected messages.
    """

    def __init__(self, print_to_console: bool = True):
        """Initialize the Messages instance.

        Args:
            print_to_console: Whether to print messages to the console. Defaults to True.
        """
        self.print_to_console = print_to_console
        self.list_of_messages = []

    @property
    def is_empty(self) -> bool:
        """Check if no messages have been recorded.

        Returns:
            True if no messages have been recorded, False otherwise.
        """
        return True if len(self.list_of_messages) == 0 else False

    def msg(self, message: Union[str, List[str]]) -> None:
        """Add a message or list of messages to the collection.

        Args:
            message: A string or list of strings to add. If a list is provided,
                each string is added separately.

        Raises:
            ValueError: If the message is not a string or list.
        """
        if isinstance(message, str):
            self._append_string(message)
        elif isinstance(message, list):
            for m in message:
                self._append_string(str(m))
        else:
            raise ValueError("Data type is not a string or a list.")

    def _append_string(self, the_string: str) -> None:
        """Add a string to the internal storage and optionally print to console.

        Args:
            the_string: The string to add to the internal message list.
        """
        if self.print_to_console:
            print(the_string + "\n")
        self.list_of_messages.append(the_string)

    def write_to_file(self, file: Optional[Path] = None) -> None:
        """Write the collected messages to a file.

        Args:
            file: Path to the target file. If not provided, the method silently does nothing.
        """
        if file is not None:
            print(f"Writing log to {file}\n")
            with open(file, "w") as f:
                f.write("\n".join(self.list_of_messages))


def wipe() -> None:
    """Clear the console by printing multiple newlines.

    Creates visual space on the console by printing 1000 newline characters.
    Based on: https://stackoverflow.com/a/517992
    """
    print("\n" * 1000)


def get_data_path() -> Path:
    """Return the local path to the data folder as declared in the configuration file.

    Returns:
        The path to the data folder as specified in tgftools.conf.

    Raises:
        AssertionError: If the configuration file tgftools.conf does not exist.
    """
    CONFIG_FILE = get_root_path() / "tgftools.conf"
    assert (
        CONFIG_FILE.exists()
    ), "The configuration file `tgftools.conf` does not exist."
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    return Path(config["DEFAULT"].get("DATA_FOLDER_PATH"))


def get_output_path() -> Path:
    """Return the local path to the outputs folder.

    Returns:
        The path to the outputs folder within the repository root.
    """
    return get_root_path() / "outputs"


def save_var(var: Any, target_file: Optional[Path] = None) -> None:
    """Save a variable to a file using pickle serialization.

    Args:
        var: The variable to save.
        target_file: Path to the target file. If not provided, defaults to
            root/sessions/tmp.pkl. If the file exists, it will be overwritten.
    """
    filename = (
        target_file
        if target_file is not None
        else get_root_path() / "sessions" / "tmp.pkl"
    )
    with open(filename, "wb") as f:
        dill.dump(var, f)


def load_var(target_file: Optional[Path] = None) -> Any:
    """Load a variable from a pickle file.

    Args:
        target_file: Path to the file to load. If not provided, defaults to
            root/sessions/tmp.pkl.

    Returns:
        The deserialized variable from the file.
    """
    filename = (
        target_file
        if target_file is not None
        else get_root_path() / "sessions" / "tmp.pkl"
    )
    with open(filename, "rb") as f:
        return dill.load(f)


def current_date_and_time_as_string() -> str:
    """Return the current date and time as a formatted string.

    Returns:
        A string representing the current date and time in the format "YYYY-MM-DD HH:MM:SS".
    """
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


def open_file(file: Path) -> None:
    """Open a file using the operating system's default application.

    Args:
        file: Path to the file to open.

    Note:
        Based on: https://stackoverflow.com/questions/434597/open-document-with-default-application-in-python/435669#435669
    """
    if platform.system() == "Darwin":  # macOS
        subprocess.call(("open", file))
    elif platform.system() == "Windows":  # Windows
        os.startfile(file)
    else:  # Linux variants
        subprocess.call(("xdg-open", file))


def deEmojify(text: str) -> str:
    """Remove emoji characters from text.

    Args:
        text: The text string from which to remove emojis.

    Returns:
        The input text with all emoji characters removed.
    """
    emoji = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Symbols & pictographs
        "\U0001F680-\U0001F6FF"  # Transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # Flags (iOS)
        "\U00002500-\U00002BEF"  # Chinese characters
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # Dingbats
        "\u3030"
        "]+",
        re.UNICODE,
    )
    return re.sub(emoji, "", text)


def matmul(a: np.ndarray) -> np.ndarray:
    """Compute the matrix multiplication of an array and its transpose.

    This function reproduces the behavior of the MMULT command in Google Sheets
    when applied to a 1-dimensional array.

    Args:
        a: A 1-dimensional numpy array.

    Returns:
        A 2-dimensional square matrix resulting from multiplying the column vector
        form of the array by its row vector form (a @ a.T).

    Raises:
        AssertionError: If the input array is not 1-dimensional.
    """
    assert a.shape == (len(a),)
    return a.reshape(len(a), 1).dot(a.reshape(1, len(a)))
