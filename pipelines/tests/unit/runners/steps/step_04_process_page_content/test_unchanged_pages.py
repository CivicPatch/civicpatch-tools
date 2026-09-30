"""The hash gate: an unchanged page reuses its published verdict and records, with no LLM call."""

from unittest.mock import AsyncMock, patch

import pytest
from runners.people_collector.schemas import Link, LinkFrontier, LinkStatus, RelevantPageResponseSchema
from runners.people_collector.steps.step_04_process_page_content.unchanged_pages import (
    is_unchanged,
    published_source_page,
)
from runners.people_collector.steps.step_04_process_page_content.process_page_content import (
    process_page_content,
)
from shared.schemas import PublishedSourcePage, PersonSourceRecord
from shared.utils.url_utils import canonical_url
from tests.factories.pipeline_run_context import pipeline_run_context_factory

pytestmark = pytest.mark.unit

_MODULE = "runners.people_collector.steps.step_04_process_page_content.process_page_content"
_URL = "https://seattle.gov/council"
_READ = "row-where-the-llm-read-it"


def _known(**fields) -> PublishedSourcePage:
    return PublishedSourcePage(
        **{
            "source_url": _URL,
            "read_source_page_id": _READ,
            "page_hash": "p",
            "prompt_hash": "q",
            "is_relevant": True,
            **fields,
        }
    )


# --- the rule ------------------------------------------------------------------------------


def test_the_same_page_and_prompts_are_unchanged():
    assert is_unchanged(_known(), "p", "q") is True


def test_a_changed_page_is_read_fresh():
    assert is_unchanged(_known(), "changed", "q") is False


def test_changed_prompts_are_read_fresh():
    """A renamed organization or a reworded prompt: the old answer was to another question."""
    assert is_unchanged(_known(), "p", "changed") is False


def test_another_page_has_no_stored_reading_here():
    assert published_source_page([_known()], "https://seattle.gov/mayor") is None


def test_the_same_page_spelled_differently_still_finds_its_reading():
    assert published_source_page([_known()], _URL + "/") == _known()


# --- through step 4 ------------------------------------------------------------------------


def _context(tmp_path, published_source_pages: list[PublishedSourcePage]):
    (tmp_path / "council").mkdir(exist_ok=True)
    (tmp_path / "council" / "preprocessed.md").write_text("# Council", encoding="utf-8")
    page = Link(url=_URL, status=LinkStatus.PREPROCESSED.value, folder_name="council")
    context = pipeline_run_context_factory(steps={})
    data = context.data.model_copy(
        update={
            "frontier": LinkFrontier(links={canonical_url(_URL): page}),
            "config": context.data.config.model_copy(update={"published_source_pages": published_source_pages}),
        }
    )
    return context.model_copy(update={"data": data}), page


async def _step_4(tmp_path, published_source_pages: list[PublishedSourcePage], llm: AsyncMock):
    context, page = _context(tmp_path, published_source_pages)
    with (
        patch(f"{_MODULE}.data_path_utils.get_cache_path", return_value=str(tmp_path)),
        patch(f"{_MODULE}.open_router_llm.run_prompt", new=llm),
    ):
        frontier, step = await process_page_content(context, page)
    return frontier.get(_URL), step


def _irrelevant_llm() -> AsyncMock:
    return AsyncMock(
        return_value=RelevantPageResponseSchema(is_relevant=False, relevant_urls=[]).model_dump()
    )


async def _this_pages_hashes(tmp_path) -> tuple[str, str]:
    """Read once for real, so the test reuses exactly the hashes step 4 computes."""
    link, _ = await _step_4(tmp_path, [], _irrelevant_llm())
    return link.page_hash, link.prompt_hash


@pytest.mark.asyncio
async def test_an_unchanged_irrelevant_page_calls_no_llm(tmp_path):
    page_hash, prompt_hash = await _this_pages_hashes(tmp_path)
    llm = _irrelevant_llm()

    link, _ = await _step_4(
        tmp_path,
        [_known(page_hash=page_hash, prompt_hash=prompt_hash, is_relevant=False)],
        llm,
    )

    assert llm.await_count == 0
    assert link.status == LinkStatus.PROCESSED_IRRELEVANT.value
    assert link.unchanged_since_source_page_id == _READ


@pytest.mark.asyncio
async def test_an_unchanged_relevant_page_replays_its_people_with_their_photos(tmp_path):
    """The replay is a full reading: skip it and these people look absent, then retire."""
    page_hash, prompt_hash = await _this_pages_hashes(tmp_path)
    ana = PersonSourceRecord(
        name="Ana Reyes",
        label="Council Member",
        source_url=_URL,
        organization_id="council",
        image="https://seattle.gov/ana.jpg",
        cdn_image="https://artifacts.example/run-0/ana.jpg",
    )
    llm = _irrelevant_llm()

    link, step = await _step_4(
        tmp_path,
        [
            _known(
                page_hash=page_hash,
                prompt_hash=prompt_hash,
                organization_ids=["council"],
                known_records=[ana],
            )
        ],
        llm,
    )

    assert llm.await_count == 0
    assert link.status == LinkStatus.DONE.value
    assert (link.organization_ids, link.unchanged_since_source_page_id) == (["council"], _READ)
    [record] = [record for records in step.records.values() for record in records]
    assert (record.name, record.cdn_image) == ("Ana Reyes", ana.cdn_image)


@pytest.mark.asyncio
async def test_a_page_that_changed_since_is_read_again(tmp_path):
    _, prompt_hash = await _this_pages_hashes(tmp_path)
    llm = _irrelevant_llm()

    link, _ = await _step_4(
        tmp_path, [_known(page_hash="old", prompt_hash=prompt_hash, is_relevant=False)], llm
    )

    assert llm.await_count == 1
    assert link.unchanged_since_source_page_id is None
