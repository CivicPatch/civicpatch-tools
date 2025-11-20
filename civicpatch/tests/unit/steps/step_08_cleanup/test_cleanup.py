import os
import pytest
from unittest.mock import MagicMock, patch, mock_open
from steps.step_08_cleanup.cleanup import cleanup_images
from schemas import Person

pytestmark = pytest.mark.unit

# Person factory for creating test instances
def person_factory(image=None, sources=None, website=None):
    return Person(
        image=image,
        roles=[],
        divisions=[],
        jurisdiction_id="",
        sources=sources or [],
        website=website,
        # Add other attributes as needed with default values
        name="Test Person",
        email=None,
        updated_at="",
    )

@pytest.fixture
def mock_logger():
    return MagicMock()

@pytest.fixture
def mock_request_id():
    return "test_request"

@pytest.fixture
def mock_jurisdiction_id():
    return "test_jurisdiction"

@pytest.fixture
def mock_images_dir():
    return "/mock/images"

@patch("os.listdir")
@patch("os.path.isfile")
@patch("os.path.getsize")
@patch("builtins.open", new_callable=mock_open, read_data='''{
    "https://example.com/image1.jpg": "/mock/images/mapped_image1.jpg",
    "https://example.com/image2.jpg": "/mock/images/mapped_image2.jpg"
}''')
@patch("os.remove")
@patch("utils.cost_utils.add_storage_cost")
def test_cleanup_images_respects_image_map(
    mock_add_storage_cost, mock_remove, mock_open_file, mock_getsize, mock_isfile, mock_listdir,
    mock_logger, mock_request_id, mock_jurisdiction_id, mock_images_dir
):
    # Mock inputs
    people_list = [
        person_factory(image="https://example.com/image1.jpg"),
        person_factory(image="https://example.com/image2.jpg"),
    ]

    # Mock directory structure
    mock_listdir.return_value = [
        "mapped_image1.jpg",
        "mapped_image2.jpg",
        "unmapped_image.jpg",
        "image_map.json"
    ]
    mock_isfile.side_effect = lambda path: not path.endswith("image_map.json")
    mock_getsize.return_value = 1024

    # Call the function
    cleanup_images(mock_logger, mock_request_id, mock_jurisdiction_id, mock_images_dir, people_list)

    # Assertions
    mock_listdir.assert_called_once_with(mock_images_dir)
    mock_open_file.assert_called_once_with(os.path.join(mock_images_dir, "image_map.json"), "r")
    mock_add_storage_cost.assert_any_call(
        request_id=mock_request_id,
        jurisdiction_id=mock_jurisdiction_id,
        file_size_bytes=1024
    )

    # Ensure unreferenced files are removed
    mock_remove.assert_called_once_with(os.path.join(mock_images_dir, "unmapped_image.jpg"))

    # Ensure mapped files are not removed
    removed_files = [call.args[0] for call in mock_remove.call_args_list]
    assert os.path.join(mock_images_dir, "mapped_image1.jpg") not in removed_files
    assert os.path.join(mock_images_dir, "mapped_image2.jpg") not in removed_files
