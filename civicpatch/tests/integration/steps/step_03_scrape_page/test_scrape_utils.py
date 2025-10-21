import os
import pytest
import shutil
from unittest.mock import AsyncMock, MagicMock, patch
from steps.step_03_scrape_page.scrape_utils import download_images, scrape

pytestmark = pytest.mark.integration

# Dynamically determine the directory of the test file
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(TEST_DIR, "fixtures")

@pytest.fixture(autouse=True)
def clean_fixtures_dir():
    """
    Ensure the fixtures directory is clean before each test.
    """
    if os.path.exists(FIXTURES_DIR):
        shutil.rmtree(FIXTURES_DIR)  # Remove existing fixtures directory
    os.makedirs(FIXTURES_DIR, exist_ok=True)

@pytest.mark.asyncio
async def test_scrape_with_direct_download():
    # Mock logger
    logger = MagicMock()

    # URL to scrape
    website_url = "https://www.greensboro-nc.gov/government/city-council/interact-with-city-council"

    # Options for scraping
    options = {
        "image_directory": FIXTURES_DIR,
        "scraped_urls": []
    }

    # Run the scrape function
    try:
        await scrape(logger, website_url, options)
    except Exception as e:
        pytest.fail(f"Scrape function raised an exception: {e}")

    # Check if images were downloaded
    downloaded_files = os.listdir(FIXTURES_DIR)
    assert len(downloaded_files) > 0, "No files were downloaded."
    assert "image_map.json" in downloaded_files, "Image map file is missing."
    assert_logger_called_with_partial(logger, "Image downloaded directly: ")

    # Verify logger calls with partial matching

def assert_logger_called_with_partial(logger, partial_message):
    """
    Helper function to assert that a partial message exists in the logger's calls.
    """
    assert any(partial_message in str(call) for call in logger.info.call_args_list), (
        f"Logger did not log a message containing: {partial_message}"
    )