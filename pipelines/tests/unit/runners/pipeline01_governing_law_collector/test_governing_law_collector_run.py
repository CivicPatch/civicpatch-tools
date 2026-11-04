"""A whole governing_law_collector run through the engine, with its edges faked: the finder,
the fetcher and cp.org. What is under test is the walk through its graph."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from runners.engine import PipelineRunError, run_pipeline, terminal_states
from runners.pipeline01_governing_law_collector.fetchers import OffLimits, RefusedByHost
from runners.pipeline01_governing_law_collector.main import MACHINE
from runners.pipeline01_governing_law_collector.schemas import (
    FetchedPage,
    FinderAnswer,
    GoverningLawCollectorConfig,
    GoverningLawCollectorContext,
    GoverningLawCollectorData,
    TriedReason,
    TriedUrl,
)
from runners.pipeline01_governing_law_collector.transitions.graph import (
    GOVERNING_LAW_COLLECTOR_TRANSITIONS,
)
from runners.pipeline01_governing_law_collector.transitions.main import TRANSITION_MAP
from shared.schemas import FoundBy, GoverningLawKind
from shared.utils.layered_config import GoverningLawConfig
from shared.utils.statuses import TERMINAL_PIPELINE_RUN_STATUSES, PipelineRunStatus

pytestmark = pytest.mark.unit

MAIN = "runners.pipeline01_governing_law_collector.transitions.main"
_OCDID = "ocd-jurisdiction/country:us/state:vt/place:stowe/government"
_CHARTER = "https://legislature.vermont.gov/statutes/fullchapter/24APPENDIX/153"
_STATUTE = "https://legislature.vermont.gov/statutes/section/17/055/02646"
_TEXT = "# Chapter 153\n\n" + "§ 1. Corporate existence retained. " * 20


_OREGON = GoverningLawConfig.model_validate({
    "charter_terms": ["Charter"],
    "classifications": {"county": {"lsad": ["county"], "governed_by": "charter_else_general_law", "general_law": [_STATUTE]}},
})


def _context(config: GoverningLawCollectorConfig | None = None) -> GoverningLawCollectorContext:
    return GoverningLawCollectorContext(
        pipeline_run_id="run-1",
        current_state=PipelineRunStatus.INIT,
        data=GoverningLawCollectorData(
            jurisdiction_ocdid=_OCDID, config=config or GoverningLawCollectorConfig(name="Stowe town", governing_law=None)
        ),
    )


def _html(url: str, body: str, by_browser: bool = False) -> FetchedPage:
    return FetchedPage(url=url, content_type="text/html", body=f"<html><body><article>{body}</article></body></html>".encode(), by_browser=by_browser)


async def _run(
    answer: FinderAnswer, fetch, reusable: dict[str, str] | None = None, config: GoverningLawCollectorConfig | None = None
) -> tuple[GoverningLawCollectorContext, MagicMock]:
    """`reusable` maps a url to the row id another run stored for it within a day."""
    stored = iter(f"page-{n}" for n in range(1, 10))
    reusable = reusable or {}
    api = MagicMock()
    api.reuse_governing_law_source_page = AsyncMock(side_effect=lambda _client, _ocdid, url: {"id": reusable[url]} if url in reusable else None)
    api.store_governing_law_source_page = AsyncMock(side_effect=lambda *_: {"id": next(stored)})
    api.patch_jurisdiction_extras = AsyncMock()
    engine_api = MagicMock()
    engine_api.fetch_pipeline_run_status = AsyncMock(return_value=PipelineRunStatus.RUNNING)
    engine_api.update_pipeline_run_status = AsyncMock()
    with patch(f"{MAIN}.civicpatch_api", api), patch("runners.engine.civicpatch_api", engine_api), patch(
        "runners.engine.log_system_usage"
    ), patch(f"{MAIN}.finders.find", new=AsyncMock(return_value=answer)), patch(f"{MAIN}.fetchers.fetch", new=fetch):
        context = await run_pipeline(_context(config), MagicMock(), MACHINE, AsyncMock())
    return context, api


def test_the_graph_ends_where_every_run_ends_and_every_state_has_a_handler():
    before_the_engine = {PipelineRunStatus.PENDING, PipelineRunStatus.RUNNING}
    handled = {state for state, allowed in GOVERNING_LAW_COLLECTOR_TRANSITIONS.items() if allowed and state not in before_the_engine}

    assert set(terminal_states(GOVERNING_LAW_COLLECTOR_TRANSITIONS)) == set(TERMINAL_PIPELINE_RUN_STATUSES)
    assert set(TRANSITION_MAP) == handled


@pytest.mark.asyncio
async def test_a_charter_is_fetched_converted_stored_and_written():
    answer = FinderAnswer(found_by=FoundBy.STATE_INDEX, classification="town", charter_urls=[_CHARTER])
    fetch = AsyncMock(return_value=_html(_CHARTER, _TEXT))

    context, api = await _run(answer, fetch)

    assert context.current_state == PipelineRunStatus.SUCCESS
    stored_text = api.store_governing_law_source_page.await_args.args[3]
    assert "<" not in stored_text and "Corporate existence retained" in stored_text
    written = api.patch_jurisdiction_extras.await_args.args[2].extras_governing_law
    assert (written.kind, written.found_by, written.classification, written.source_page_ids) == (
        GoverningLawKind.CHARTER, FoundBy.STATE_INDEX, "town", ["page-1"]
    )


@pytest.mark.asyncio
async def test_nothing_to_fetch_is_written_as_none_found():
    answer = FinderAnswer(found_by=FoundBy.CLASSIFICATION, classification=None)
    fetch = AsyncMock()

    context, api = await _run(answer, fetch)

    assert context.current_state == PipelineRunStatus.SUCCESS
    fetch.assert_not_awaited()
    assert api.patch_jurisdiction_extras.await_args.args[2].extras_governing_law.kind == GoverningLawKind.NONE_FOUND


@pytest.mark.asyncio
async def test_a_search_that_confirmed_no_charter_writes_the_statutes_it_stored_and_fails():
    tried = [TriedUrl(url="https://www.lanecountyor.gov", reason=TriedReason.SITE_CRAWLED)]
    answer = FinderAnswer(found_by=FoundBy.SEARCH, classification="county", general_law_urls=[_STATUTE], tried=tried)
    fetch = AsyncMock(side_effect=lambda url, by_browser: _html(url, _TEXT))

    with pytest.raises(PipelineRunError) as failed:
        await _run(answer, fetch, config=GoverningLawCollectorConfig(name="Lane County", governing_law=_OREGON))

    written = failed.value.context.data.governing_law
    assert written is not None and written.kind == GoverningLawKind.GENERAL_LAW


@pytest.mark.asyncio
async def test_a_refusal_skips_that_url_and_is_never_retried_by_browser():
    answer = FinderAnswer(found_by=FoundBy.STATE_INDEX, classification="town", charter_urls=[_CHARTER], general_law_urls=[_STATUTE])

    async def fetch(url, by_browser):
        if url == _CHARTER:
            raise RefusedByHost(url, 403)
        return _html(url, _TEXT)

    spy = AsyncMock(side_effect=fetch)
    context, api = await _run(answer, spy)

    assert [call.args for call in spy.await_args_list] == [(_CHARTER,), (_STATUTE,)]
    assert all(call.kwargs == {"by_browser": False} for call in spy.await_args_list)
    assert context.data.skipped_urls == [_CHARTER]
    assert api.patch_jurisdiction_extras.await_args.args[2].extras_governing_law.source_page_ids == ["page-1"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        httpx.HTTPStatusError("404", request=httpx.Request("GET", _CHARTER), response=httpx.Response(404)),
        httpx.ConnectError("certificate verify failed"),
        httpx.ReadTimeout("timed out"),
        OffLimits("http://10.0.0.5/charter"),
    ],
    ids=["404", "tls", "timeout", "off-limits"],
)
async def test_a_url_that_fails_to_fetch_is_skipped_and_the_next_one_stored(error: Exception):
    answer = FinderAnswer(found_by=FoundBy.STATE_INDEX, classification="town", charter_urls=[_CHARTER], general_law_urls=[_STATUTE])

    async def fetch(url, by_browser):
        if url == _CHARTER:
            raise error
        return _html(url, _TEXT)

    context, api = await _run(answer, AsyncMock(side_effect=fetch))

    assert context.current_state == PipelineRunStatus.SUCCESS
    assert context.data.skipped_urls == [_CHARTER]
    written = api.patch_jurisdiction_extras.await_args.args[2].extras_governing_law
    assert (written.kind, written.source_page_ids) == (GoverningLawKind.GENERAL_LAW, ["page-1"])


@pytest.mark.asyncio
async def test_a_page_with_no_converter_is_skipped_and_the_next_one_stored():
    answer = FinderAnswer(found_by=FoundBy.STATE_INDEX, classification="town", charter_urls=[_CHARTER], general_law_urls=[_STATUTE])

    async def fetch(url, by_browser):
        if url == _CHARTER:
            return FetchedPage(url=url, content_type="application/pdf", body=b"%PDF-1.7", by_browser=False)
        return _html(url, _TEXT)

    spy = AsyncMock(side_effect=fetch)
    context, api = await _run(answer, spy)

    assert context.current_state == PipelineRunStatus.SUCCESS
    assert [call.args for call in spy.await_args_list] == [(_CHARTER,), (_STATUTE,)]
    assert context.data.skipped_urls == [_CHARTER]
    assert api.patch_jurisdiction_extras.await_args.args[2].extras_governing_law.source_page_ids == ["page-1"]


@pytest.mark.asyncio
async def test_a_nearly_empty_page_is_fetched_once_more_by_browser():
    answer = FinderAnswer(found_by=FoundBy.STATE_INDEX, classification="town", charter_urls=[_CHARTER])

    async def fetch(url, by_browser):
        return _html(url, _TEXT, by_browser=True) if by_browser else _html(url, "Loading…")

    spy = AsyncMock(side_effect=fetch)
    context, _ = await _run(answer, spy)

    assert [call.kwargs["by_browser"] for call in spy.await_args_list] == [False, True]
    assert context.data.charter_source_page_ids == ["page-1"]


@pytest.mark.asyncio
async def test_urls_none_of_which_could_be_stored_write_none_found_and_fail_the_run():
    answer = FinderAnswer(found_by=FoundBy.STATE_INDEX, classification="town", charter_urls=[_CHARTER])
    fetch = AsyncMock(side_effect=RefusedByHost(_CHARTER, 429))

    with pytest.raises(PipelineRunError) as failed:
        await _run(answer, fetch)

    written = failed.value.context.data.governing_law
    assert written is not None and written.kind == GoverningLawKind.NONE_FOUND



@pytest.mark.asyncio
async def test_a_charter_with_its_general_law_is_a_charter_with_both_pages():
    answer = FinderAnswer(found_by=FoundBy.STATE_INDEX, classification="town", charter_urls=[_CHARTER], general_law_urls=[_STATUTE])
    fetch = AsyncMock(side_effect=lambda url, by_browser: _html(url, _TEXT))

    _, api = await _run(answer, fetch)

    written = api.patch_jurisdiction_extras.await_args.args[2].extras_governing_law
    assert (written.kind, written.source_page_ids) == (GoverningLawKind.CHARTER, ["page-1", "page-2"])




@pytest.mark.asyncio
async def test_a_page_another_run_stored_today_is_not_fetched_again():
    answer = FinderAnswer(found_by=FoundBy.STATE_INDEX, classification="town", charter_urls=[_CHARTER], general_law_urls=[_STATUTE])
    fetch = AsyncMock(side_effect=lambda url, by_browser: _html(url, _TEXT))

    context, api = await _run(answer, fetch, reusable={_STATUTE: "stowes-statute"})

    assert [call.args for call in fetch.await_args_list] == [(_CHARTER,)]
    assert context.data.general_law_source_page_ids == ["stowes-statute"]
    assert api.patch_jurisdiction_extras.await_args.args[2].extras_governing_law.source_page_ids == ["page-1", "stowes-statute"]

