import os
import pytest
from unittest.mock import patch, MagicMock
from utils.file_utils import find_file, zip_directory

pytestmark = pytest.mark.unit

@pytest.fixture
def mock_run_in_executor(mocker):
    return mocker.patch("asyncio.get_event_loop")

@patch("utils.file_utils._zip_directory_sync")
def test_zip_directory(mock_zip_directory_sync, mock_run_in_executor):
    # Mock the event loop and the synchronous zip function
    mock_loop = MagicMock()
    mock_run_in_executor.return_value = mock_loop
    mock_loop.run_in_executor.return_value = "/tmp/test.zip"

    # Call the function
    result = pytest.run(zip_directory("/test_dir", "test.zip"))

    # Assertions
    mock_loop.run_in_executor.assert_called_once_with(None, mock_zip_directory_sync, "/test_dir", "test.zip")
    assert result == "/tmp/test.zip"

@pytest.fixture
def mock_os_walk(mocker):
    return mocker.patch("os.walk")

def test_find_file_success(mock_os_walk):
    # Mock os.walk to simulate directory structure
    mock_os_walk.return_value = [
        ("/test_dir", ["subdir"], ["file1.yml", "file2.yml"]),
        ("/test_dir/subdir", [], ["file3.yml"]),
    ]

    # Test case where file is found
    result = find_file("/test_dir", "subdir/*.yml")
    assert result == "/test_dir/subdir/file3.yml"

def test_find_file_not_found(mock_os_walk):
    # Mock os.walk to simulate empty directory
    mock_os_walk.return_value = [
        ("/test_dir", ["subdir"], []),
    ]

    # Test case where file is not found
    with pytest.raises(FileNotFoundError, match="No file matching pattern 'subdir/*.yml' found in directory '/test_dir'"):
        find_file("/test_dir", "subdir/*.yml")

def test_find_file_multiple_matches(mock_os_walk):
    # Mock os.walk to simulate multiple matching files
    mock_os_walk.return_value = [
        ("/test_dir", ["subdir"], ["file1.yml", "file2.yml"]),
        ("/test_dir/subdir", [], ["file3.yml", "file4.yml"]),
    ]

    # Test case where multiple files match
    result = find_file("/test_dir", "subdir/*.yml")
    assert result == "/test_dir/subdir/file3.yml"  # Returns the first match