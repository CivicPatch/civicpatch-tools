import os
import pytest
import shutil
from unittest.mock import MagicMock
from jobs.people_collector.steps.step_03_scrape_page.scrape_utils import scrape, inline_iframes

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
    assert any("Image saved:" in str(call) for call in logger.info.call_args_list), \
        "Logger did not log an image save message"


@pytest.mark.asyncio
async def test_scrape_inlines_iframe_content():
    """
    Alcona Township officials page embeds its content in a Google Doc iframe.
    After scraping, the <iframe> tag should be replaced with the doc's body content.
    """
    logger = MagicMock()
    website_url = "https://alconatownship.com/officials/"
    options = {"scraped_urls": []}

    html_output = await scrape(logger, website_url, options)

    assert "<iframe" not in html_output, "iframe tag should have been replaced by inline_iframes"
    # The Google Doc contains text about township officials — spot-check a word that
    # appears in any township officials list.
    assert any(word in html_output.lower() for word in ["supervisor", "treasurer", "clerk", "trustee"]), \
        "expected township official role text to be inlined from the Google Doc iframe"