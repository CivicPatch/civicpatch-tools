import os
import pytest
import shutil
from unittest.mock import MagicMock
from patchright.async_api import async_playwright
from runners.people_collector.steps.step_03_scrape_page.scrape_utils import scrape, convert_background_divs_to_imgs

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
async def test_convert_background_divs_to_imgs_preserves_children():
    """
    Regression test: convert_background_divs_to_imgs must inject an <img> for the
    background-image URL without destroying the div's child elements.

    Previously used div.replaceWith(img) which wiped child content (e.g. board member
    names rendered by Avada/Fusion Builder inside background-image divs).
    """
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir="",
            channel="chrome",
            headless=True,
            no_viewport=True,
        )
        page = await context.new_page()
        await page.set_content("""
            <div style="background-image: url('https://example.com/hero.jpg')">
                <span class="member-name">Jerry Adams</span>
            </div>
        """)
        await convert_background_divs_to_imgs(page)
        img = await page.query_selector("div > img")
        span = await page.query_selector("div > span.member-name")
        assert img is not None, "<img> was not injected"
        assert await img.get_attribute("src") == "https://example.com/hero.jpg"
        assert span is not None, "child <span> was destroyed by convert_background_divs_to_imgs"
        assert await span.inner_text() == "Jerry Adams"
        await context.close()


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

    html_output, _ = await scrape(logger, website_url, options)

    assert "<iframe" not in html_output, "iframe tag should have been replaced by inline_iframes"
    # The Google Doc contains text about township officials — spot-check a word that
    # appears in any township officials list.
    assert any(word in html_output.lower() for word in ["supervisor", "treasurer", "clerk", "trustee"]), \
        "expected township official role text to be inlined from the Google Doc iframe"