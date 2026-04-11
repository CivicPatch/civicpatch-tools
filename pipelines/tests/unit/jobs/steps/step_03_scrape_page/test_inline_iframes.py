import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from jobs.people_collector.steps.step_03_scrape_page.scrape_utils import inline_iframes

pytestmark = pytest.mark.unit


def make_page(main_frame, extra_frames=None):
    page = MagicMock()
    page.main_frame = main_frame
    page.frames = [main_frame] + (extra_frames or [])
    page.evaluate = AsyncMock()
    return page


def make_frame(url, body_html="<p>content</p>", evaluate_raises=None):
    frame = MagicMock()
    frame.url = url
    if evaluate_raises:
        frame.evaluate = AsyncMock(side_effect=evaluate_raises)
    else:
        frame.evaluate = AsyncMock(return_value=body_html)
    return frame


@pytest.mark.asyncio
async def test_inline_iframes_replaces_matching_iframe():
    logger = MagicMock()
    main_frame = make_frame("https://example.com")
    child_frame = make_frame("https://docs.google.com/document/pub", "<p>Officials list</p>")
    page = make_page(main_frame, [child_frame])

    await inline_iframes(page, logger)

    child_frame.evaluate.assert_awaited_once_with("document.body.innerHTML")
    page.evaluate.assert_awaited_once()
    call_args = page.evaluate.call_args[0]
    assert call_args[1] == ["https://docs.google.com/document/pub", "<p>Officials list</p>"]
    logger.debug.assert_called_once()


@pytest.mark.asyncio
async def test_inline_iframes_no_child_frames_is_noop():
    logger = MagicMock()
    main_frame = make_frame("https://example.com")
    page = make_page(main_frame)

    await inline_iframes(page, logger)

    page.evaluate.assert_not_awaited()
    logger.debug.assert_not_called()
    logger.warning.assert_not_called()


@pytest.mark.asyncio
async def test_inline_iframes_swallows_per_frame_error():
    logger = MagicMock()
    main_frame = make_frame("https://example.com")
    bad_frame = make_frame("https://cross-origin.com", evaluate_raises=Exception("access denied"))
    good_frame = make_frame("https://other.com", "<p>good content</p>")
    page = make_page(main_frame, [bad_frame, good_frame])

    await inline_iframes(page, logger)

    logger.warning.assert_called_once()
    assert "access denied" in logger.warning.call_args[0][0]
    # good_frame should still be processed
    page.evaluate.assert_awaited_once()


@pytest.mark.asyncio
async def test_inline_iframes_multiple_frames_all_inlined():
    logger = MagicMock()
    main_frame = make_frame("https://example.com")
    frame_a = make_frame("https://a.com", "<p>A</p>")
    frame_b = make_frame("https://b.com", "<p>B</p>")
    page = make_page(main_frame, [frame_a, frame_b])

    await inline_iframes(page, logger)

    assert page.evaluate.await_count == 2
    assert logger.debug.call_count == 2
