import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock
from bs4 import BeautifulSoup
from runners.people_collector.steps.step_02_scrape_page.scrape_utils import scrape

pytestmark = [pytest.mark.live, pytest.mark.asyncio]


@pytest.mark.asyncio
async def test_rives_board_page_contains_board_members():
    """
    Rives Township's board page lazy-renders its member list after initial load.
    This test verifies the scraper captures it within the post-content body,
    not just in meta description tags.

    Passes image_directory to match real pipeline conditions — without it,
    convert_background_divs_to_imgs is skipped and the test would be a false positive.

    Run manually: mise run tlive
    Never run in CI.
    """
    logger = MagicMock()
    image_dir = tempfile.mkdtemp()
    try:
        html, _ = await scrape(logger, "https://rivestownshipmi.com/board/", {"image_directory": image_dir})
    finally:
        shutil.rmtree(image_dir, ignore_errors=True)

    soup = BeautifulSoup(html, "html.parser")
    post_content = soup.find(class_="post-content")
    assert post_content is not None, "Could not find .post-content element in scraped HTML"

    body_text = post_content.get_text()
    expected = [
        "Jerry Adams",
        "Kendra Adams",
        "Carol Schulz",
        "Brandon Adams",
        "Bryce Hammond",
        "supervisor@rivestwp.org",
        "clerk@rivestwp.org",
        "treasurer@rivestwp.org",
        "trustee1@rivestwp.org",
        "trustee2@rivestwp.org",
    ]
    missing = [s for s in expected if s not in body_text]
    assert not missing, f"Missing from .post-content body: {missing}"
