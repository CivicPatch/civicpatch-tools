import pytest
import asyncio
from utils import scrape_utils

@pytest.mark.asyncio
async def test_scrape_returns_html(tmp_path):
    url = "https://example.com"
    options = {
        "image_directory": str(tmp_path / "images"),
        "scraped_urls": []
    }
    html = await scrape_utils.scrape(url, options)

    print("Scraped HTML content:", html)  # Debugging line
    assert "<html" in html.lower()
    assert "example" in html.lower()
    # Check images directory created
    assert (tmp_path / "images").exists()