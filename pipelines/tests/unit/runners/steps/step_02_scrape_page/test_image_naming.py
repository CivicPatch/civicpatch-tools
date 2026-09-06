import os

import pytest
from unittest.mock import AsyncMock, MagicMock

from runners.people_collector.steps.step_02_scrape_page.scrape_images import (
    _register_image,
    hash_file,
)

pytestmark = pytest.mark.unit


def write_temp(tmp_path, name, content):
    path = os.path.join(tmp_path, name)
    with open(path, "wb") as f:
        f.write(content)
    return path


def make_img():
    img = MagicMock()
    img.evaluate = AsyncMock()
    return img


def test_hash_file_is_stable_for_identical_bytes(tmp_path):
    one = write_temp(tmp_path, "one.tmp", b"same photo")
    two = write_temp(tmp_path, "two.tmp", b"same photo")
    assert hash_file(one) == hash_file(two)


def test_hash_file_differs_for_different_bytes(tmp_path):
    one = write_temp(tmp_path, "one.tmp", b"old mayor")
    two = write_temp(tmp_path, "two.tmp", b"new mayor")
    assert hash_file(one) != hash_file(two)


@pytest.mark.asyncio
async def test_register_image_names_the_file_after_its_bytes(tmp_path):
    temp_path = write_temp(tmp_path, "abc123.tmp", b"a photo")
    image_map = {}
    img = make_img()

    await _register_image(img, str(tmp_path), temp_path, image_map, "https://city.gov/a.jpg")

    expected = f"{hash_file(os.path.join(tmp_path, os.listdir(tmp_path)[0]))}.png"
    assert list(image_map) == [expected]
    assert image_map[expected] == "https://city.gov/a.jpg"
    assert not os.path.exists(temp_path)
    img.evaluate.assert_awaited_once()


@pytest.mark.asyncio
async def test_one_source_url_serving_two_photos_gets_two_files(tmp_path):
    """The bug this naming exists to prevent: a jurisdiction swaps the file behind a stable
    url, and the second photo lands on the first one's permanent CDN key."""
    url = "https://city.gov/photos/mayor.jpg"
    image_map = {}

    for content in (b"the old mayor", b"the new mayor"):
        temp_path = write_temp(tmp_path, "same-url.tmp", content)
        await _register_image(make_img(), str(tmp_path), temp_path, image_map, url)

    assert len(image_map) == 2
    assert set(image_map.values()) == {url}
