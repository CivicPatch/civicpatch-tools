import os
import pytest
from unittest.mock import patch
from runners.people_collector.schemas import Link, LinkStatus
from runners.people_collector.steps.step_03_preprocess_page_content.preprocess_page_content import preprocess_page_content
from shared.utils.url_utils import canonical_url
from shared.schemas import KnownOrganization
from tests.factories.pipeline_run_context import pipeline_run_context_factory

pytestmark = pytest.mark.unit

PAGE_URL = "https://seattle.gov/council"
FOLDER = "seattle_gov_council"


def _make_context(tmp_path, extra_links=None):
    links = {canonical_url(PAGE_URL): Link(url=PAGE_URL, status=LinkStatus.SCRAPED.value, folder_name=FOLDER)}
    if extra_links:
        links.update(extra_links)
    ctx = pipeline_run_context_factory(steps={})
    from runners.people_collector.schemas import LinkFrontier
    frontier = LinkFrontier(links=links, queue=[])
    return ctx.model_copy(update={"data": ctx.data.model_copy(update={"frontier": frontier})})


def _run(tmp_path, html: str):
    page_dir = tmp_path / FOLDER
    page_dir.mkdir()
    (page_dir / "original.html").write_text(html, encoding="utf-8")
    ctx = _make_context(tmp_path)
    page = ctx.data.frontier.get(PAGE_URL)
    with (
        patch("runners.people_collector.steps.step_03_preprocess_page_content.preprocess_page_content.data_path_utils.get_cache_path", return_value=str(tmp_path)),
        patch("runners.people_collector.steps.step_03_preprocess_page_content.preprocess_page_content.filter_content", side_effect=lambda logger, identities, html, **kw: html),
    ):
        return preprocess_page_content(ctx, page)


def test_preprocess_sets_status_to_preprocessed_when_content_exists(tmp_path):
    frontier, step = _run(tmp_path, "<html><body><p>Mayor John Smith, 555-1234</p></body></html>")
    assert frontier.get(PAGE_URL).status == LinkStatus.PREPROCESSED.value


def test_preprocess_sets_status_to_no_content_when_empty(tmp_path):
    frontier, step = _run(tmp_path, "<html><body></body></html>")
    assert frontier.get(PAGE_URL).status == LinkStatus.PREPROCESSED_NO_CONTENT.value


def test_preprocess_does_not_affect_other_links(tmp_path):
    from runners.people_collector.schemas import LinkFrontier
    other_url = "https://seattle.gov/mayor"
    page_dir = tmp_path / FOLDER
    page_dir.mkdir(exist_ok=True)
    (page_dir / "original.html").write_text("<p>content</p>", encoding="utf-8")

    frontier = LinkFrontier.from_urls([PAGE_URL, other_url])
    frontier = frontier.mark_status(PAGE_URL, LinkStatus.SCRAPED).update_link(PAGE_URL, folder_name=FOLDER)
    ctx = pipeline_run_context_factory(steps={})
    ctx = ctx.model_copy(update={"data": ctx.data.model_copy(update={"frontier": frontier})})
    page = frontier.get(PAGE_URL)

    with (
        patch("runners.people_collector.steps.step_03_preprocess_page_content.preprocess_page_content.data_path_utils.get_cache_path", return_value=str(tmp_path)),
        patch("runners.people_collector.steps.step_03_preprocess_page_content.preprocess_page_content.filter_content", side_effect=lambda logger, identities, html, **kw: html),
    ):
        frontier_out, _ = preprocess_page_content(ctx, page)

    assert frontier_out.get(other_url).status == LinkStatus.PENDING.value


def test_preprocess_returns_step_with_elapsed_time(tmp_path):
    _, step = _run(tmp_path, "<p>content</p>")
    assert len(step.elapsed_times) >= 1
    assert step.total_elapsed_time_seconds >= 0


def test_preprocess_writes_preprocessed_md(tmp_path):
    _run(tmp_path, "<html><body><p>Mayor John Smith</p></body></html>")
    assert (tmp_path / FOLDER / "preprocessed.md").exists()


def test_body_names_are_keywords_for_the_content_filter(tmp_path):
    """Filtering runs before any prompt sees the page. A section headed "Office of the Mayor"
    whose wording matches no role name was dropped here, and nothing downstream could recover
    what preprocessing threw away."""
    page_dir = tmp_path / FOLDER
    page_dir.mkdir()
    (page_dir / "original.html").write_text("<html><body><p>hi</p></body></html>", encoding="utf-8")
    ctx = _make_context(tmp_path)
    research = ctx.data.research_municipality_step
    assert research is not None
    ctx = ctx.model_copy(update={"data": ctx.data.model_copy(update={
        "research_municipality_step": research.model_copy(update={
            "known_organizations": [
                KnownOrganization(id="mayor", name="Office of the Mayor"),
                KnownOrganization(id="council", name="Board of Aldermen"),
            ],
        }),
    })})
    page = ctx.data.frontier.get(PAGE_URL)

    seen = {}
    with (
        patch("runners.people_collector.steps.step_03_preprocess_page_content.preprocess_page_content.data_path_utils.get_cache_path", return_value=str(tmp_path)),
        patch(
            "runners.people_collector.steps.step_03_preprocess_page_content.preprocess_page_content.filter_content",
            side_effect=lambda logger, identities, html, **kw: seen.update(kw) or html,
        ),
    ):
        preprocess_page_content(ctx, page)

    assert "Office of the Mayor" in seen["extra_keywords"]
    assert "Board of Aldermen" in seen["extra_keywords"]
