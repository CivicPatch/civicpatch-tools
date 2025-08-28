import os
import shutil
import zipfile
import tempfile
import pytest

from steps.step_08_maybe_send_to_github.maybe_send_to_github import zip_files

@pytest.fixture
def temp_dirs_and_files():
    # Create temp dirs and files to simulate municipality data
    temp_dir = tempfile.mkdtemp()
    muni_dir = os.path.join(temp_dir, "muni")
    source_dir = os.path.join(temp_dir, "source")
    os.makedirs(muni_dir)
    os.makedirs(source_dir)
    # Create dummy files
    muni_file = os.path.join(muni_dir, "file1.txt")
    source_file = os.path.join(source_dir, "file2.txt")
    with open(muni_file, "w") as f:
        f.write("muni data")
    with open(source_file, "w") as f:
        f.write("source data")
    yield muni_dir, source_dir, temp_dir
    shutil.rmtree(temp_dir)

def test_zip_files_creates_zip(temp_dirs_and_files, monkeypatch):
    muni_dir, source_dir, temp_dir = temp_dirs_and_files

    # Patch the data path utils to return our temp dirs
    monkeypatch.setattr(
        "steps.step_08_maybe_send_to_github.maybe_send_to_github.get_data_municipality_path",
        lambda state, geoid: muni_dir
    )
    monkeypatch.setattr(
        "steps.step_08_maybe_send_to_github.maybe_send_to_github.get_data_source_municipality_path",
        lambda state, geoid: source_dir
    )

    zip_path = zip_files("CA", "12345")
    assert os.path.exists(zip_path)
    assert zip_path.endswith(".zip")

    # Check contents of the zip
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        assert "file1.txt" in names
        assert "file2.txt" in names

    # Clean up
    os.remove(zip_path)