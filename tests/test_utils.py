import os
import pathlib
from pathlib import Path

from code_and_data_for_tests.funcs_for_test import GpTestData

from tgftools.utils import (
    Messages,
    deEmojify,
    get_data_path,
    get_files_with_extension,
    get_root_path,
    load_var,
    read_txt,
    save_var,
    get_commit_revision_number,
)

path_to_data_for_tests = (
    pathlib.Path(os.path.dirname(__file__)) / "code_and_data_for_tests"
)


def test_get_root_path():
    """`get_root_path` should return a path object."""
    path = get_root_path()
    assert isinstance(path, Path)


def test_message(tmpdir):
    """The message class should accept message and save them to a text file."""
    m = Messages()

    assert m.is_empty

    m.msg("line 1")
    m.msg("line 2")
    m.msg(["mylist_a", "mylist_b", "mylist_c"])

    target_file = tmpdir / "tmp.txt"
    m.write_to_file(target_file)

    output = read_txt(target_file)
    assert ["line 1", "line 2", "mylist_a", "mylist_b", "mylist_c"] == output

    assert not m.is_empty


def test_get_data_path():
    """`get_data_path` should return a path that exists."""
    data_path = get_data_path()
    assert isinstance(data_path, Path)
    assert (
        data_path.exists()
    ), "The path for data specified in `tgftools.conf` does not exist."


def test_get_files_with_extension():
    rtn = get_files_with_extension(path_to_data_for_tests, "csv")
    assert all([file.exists() and file.name.endswith("csv") for file in rtn])


def test_save_var_and_load_var(tmp_path):
    """Should save all the workspace variables to a file and then retrieve them."""
    from code_and_data_for_tests.funcs_for_test import ModelResultsTestData

    from tgftools.database import Database

    # file for saving:
    target_filename = tmp_path / "tmp.pkl"

    # Create a database
    db = Database(
        model_results=ModelResultsTestData(
            path_to_data_for_tests / "model_results.csv"
        ),
        gp=GpTestData(
            fixed_gp=path_to_data_for_tests / "gp.csv",
            model_results=None,
            partner_data=None,
        ),
    )

    # Save the database
    save_var(db, target_filename)

    # Load the file to restore the workspace and check equal to the original
    db_loaded = load_var(target_filename)

    assert isinstance(db_loaded, Database)

    # Check that the file is always over-written
    a = 0
    save_var(a, target_filename)
    assert 0 == load_var(target_filename)


def test_deEmojify():
    texts = ["This is a smiley face \U0001f602", "hello 👎"]

    for text in texts:
        print(text)  # with emoji
        print(deEmojify(text))


def test_get_commit():
    assert isinstance(get_commit_revision_number(), str)
