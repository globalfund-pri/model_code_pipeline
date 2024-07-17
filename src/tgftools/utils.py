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

"""This is a collection of utility functions that are used in multiple parts of the framework."""


def get_root_path(starter_path: Optional[Path] = None) -> Path:
    """Returns the absolute path of the root of the repository. `starter_path` optionally gives a reference
    location from which to begin search; if omitted the location of this file is used.
    """

    def get_git_root(path: Path) -> Path:
        """Return path of git repo. Based on: https://stackoverflow.com/a/41920796"""
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
    """Returns the commit revison number at the HEAD position in the repository currently."""
    return str(git.Repo(get_root_path()).head.commit.hexsha)


def read_txt(file) -> List:
    """Return the contents of a text file and returns a list wherein each element is a line from the text file."""
    with open(file) as f:
        lines = f.readlines()
    return list(map(lambda s: s.replace("\n", ""), lines))


def get_files_with_extension(path: Path, extension: str) -> List[Path]:
    """Return a list of the path of files that exist in a particular directory with a particular extension."""
    return list(path.glob(f"*.{extension}"))


class Messages:
    """This class is used to capture a stream of messages (strings), which are printed to the console and can also
    be written them to a text file."""

    def __init__(self, print_to_console: bool = True):
        self.print_to_console = print_to_console
        self.list_of_messages = []

    @property
    def is_empty(self) -> bool:
        """Returns True if no messages have been recorded."""
        return True if len(self.list_of_messages) == 0 else False

    def msg(self, message: Union[str, List[str]]) -> None:
        """Add a message to this class. The message can be a string or a list of strings. If a list of strings is
        provided it is equivalent to each string haven't been provided in a separate call.
        """
        if isinstance(message, str):
            self._append_string(message)
        elif isinstance(message, list):
            for m in message:
                self._append_string(str(m))
        else:
            raise ValueError("Data type is not a string or a list.")

    def _append_string(self, the_string: str) -> None:
        """Private function that adds a string to the internal storge of messages (a list) and prints it to the
        console."""
        if self.print_to_console:
            print(the_string + "\n")
        self.list_of_messages.append(the_string)

    def write_to_file(self, file: Optional[Path] = None) -> None:
        """Writes the content of the internal storage of messages to a file.
        If a target file is not provided then this will (silently) do nothing."""
        if file is not None:
            print(f"Writing log to {file}\n")
            with open(file, "w") as f:
                f.write("\n".join(self.list_of_messages))


def wipe() -> None:
    """Make some space on the console.
    From: https://stackoverflow.com/a/517992"""
    print("\n" * 1000)


def get_data_path() -> Path:
    """Returns the local path to the data folder, as declared in `tgftools.conf`."""
    CONFIG_FILE = get_root_path() / "tgftools.conf"
    assert (
        CONFIG_FILE.exists()
    ), "The configuration file `tgftools.conf` does not exist."
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    return Path(config["DEFAULT"].get("DATA_FOLDER_PATH"))


def get_output_path() -> Path:
    """Returns the local path to the outputs folder, as declared in `tgftools.conf`."""
    return get_root_path() / "outputs"


def save_var(var: Any, target_file: Optional[Path] = None) -> None:
    """Saves a variable to the specified file. If no file is provided a default is used.
    The default file is: `root / sessions / tmp.pkl`.
    If the file already exists, it is over-written.
    """
    filename = (
        target_file
        if target_file is not None
        else get_root_path() / "sessions" / "tmp.pkl"
    )
    with open(filename, "wb") as f:
        dill.dump(var, f)


def load_var(target_file: Optional[Path] = None) -> Any:
    """Loads a saved session from the specified file. If no file is provided a default is used.
    The default file is: `root / sessions / tmp.pkl`.
    """
    filename = (
        target_file
        if target_file is not None
        else get_root_path() / "sessions" / "tmp.pkl"
    )
    with open(filename, "rb") as f:
        return dill.load(f)


def current_date_and_time_as_string() -> str:
    now = datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


def open_file(file: Path) -> None:
    """Open file in operating-system default application.
    From: https://stackoverflow.com/questions/434597/open-document-with-default-application-in-python/435669#435669
    """
    if platform.system() == "Darwin":  # macOS
        subprocess.call(("open", file))
    elif platform.system() == "Windows":  # Windows
        os.startfile(file)
    else:  # linux variants
        subprocess.call(("xdg-open", file))


def deEmojify(text: str):
    """Remove emoji from the text"""
    emoji = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002500-\U00002BEF"  # chinese char
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
        "\ufe0f"  # dingbats
        "\u3030"
        "]+",
        re.UNICODE,
    )
    return re.sub(emoji, "", text)


def matmul(a: np.array) -> np.array:
    """Returns matrix multiplication of an array and its transpose, in a manner that reproduces the behaviour of the command of the same name in google sheets. """
    assert a.shape == (len(a),)
    return a.reshape(len(a), 1).dot(a.reshape(1, len(a)))
