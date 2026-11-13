import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

import runners.pipeline03_people_collector.steps.step_02_scrape_page.scrape_images as scrape_images

pytestmark = pytest.mark.unit

TILE_COUNT = 20


def make_page(srcs):
    imgs = []
    for src in srcs:
        img = MagicMock()
        img.get_attribute = AsyncMock(return_value=src)
        imgs.append(img)
    page = MagicMock()
    page.url = "https://county.gov/CO/Pages/default.aspx"
    page.evaluate = AsyncMock()
    page.query_selector_all = AsyncMock(return_value=imgs)
    return page


async def hang(*_args, **_kwargs):
    await asyncio.sleep(10)


def warnings(logger):
    return [call.args[0] for call in logger.warning.call_args_list]


@pytest.mark.asyncio
async def test_a_page_of_hanging_images_stops_at_the_page_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape_images, "load_and_save_image", hang)
    srcs = [f"/maps/vt?pb=tile{n}" for n in range(TILE_COUNT)]
    logger = MagicMock()

    await scrape_images.download_images(
        None, logger, make_page(srcs), str(tmp_path), timeout_s=0.05, page_budget_s=0.12
    )

    timeouts = [w for w in warnings(logger) if w.startswith("Timeout processing image")]
    budget = [w for w in warnings(logger) if w.startswith("Image budget")]
    assert 1 <= len(timeouts) < TILE_COUNT
    assert len(budget) == 1
    assert f"skipped the last {TILE_COUNT - len(timeouts)} of {TILE_COUNT} images" in budget[0]


@pytest.mark.asyncio
async def test_a_timeout_names_the_image(tmp_path, monkeypatch):
    monkeypatch.setattr(scrape_images, "load_and_save_image", hang)
    logger = MagicMock()

    await scrape_images.download_images(
        None, logger, make_page(["/maps/vt?pb=tile0"]), str(tmp_path), timeout_s=0.05, page_budget_s=1
    )

    assert "Timeout processing image /maps/vt?pb=tile0, skipping to next." in warnings(logger)
