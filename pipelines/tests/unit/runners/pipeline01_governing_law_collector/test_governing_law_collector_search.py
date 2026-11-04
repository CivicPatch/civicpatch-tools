"""The search finder: Gemini's urls confirmed by fetch, the crawl when none is, the statutes beside."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runners.pipeline01_governing_law_collector.fetchers import RefusedByHost
from runners.pipeline01_governing_law_collector.finders import search
from runners.pipeline01_governing_law_collector.schemas import FetchedPage, TriedReason, TriedUrl
from shared.schemas import FoundBy
from shared.utils.layered_config import GoverningLawConfig

pytestmark = pytest.mark.unit

SEARCH = "runners.pipeline01_governing_law_collector.finders.search"
_OCDID = "ocd-jurisdiction/country:us/state:or/county:lane/government"
_STATUTE = "https://www.oregonlegislature.gov/bills_laws/ors/ors203.html"
_OREGON = GoverningLawConfig.model_validate({
    "charter_terms": ["Charter", "Home Rule Charter"],
    "classifications": {"county": {"lsad": ["county"], "governed_by": "charter_else_general_law", "general_law": [_STATUTE]}},
})
_CLAUSE = "Section {n}. The board of county commissioners shall consist of five county commissioners. "
CHARTER_TEXT = "HOME RULE CHARTER FOR LANE COUNTY " + "".join(_CLAUSE.format(n=n) for n in range(1, 61))
_REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc"
_FINAL = "https://www.lanecountyor.gov/files/charter.pdf"


def _html(url: str, body: str) -> FetchedPage:
    return FetchedPage(url=url, content_type="text/html", body=f"<html><body><article>{body}</article></body></html>".encode(), by_browser=False)


async def _run(answer, fetch, url="https://www.lanecountyor.gov"):
    with patch(f"{SEARCH}.gemini.run_prompt", new=AsyncMock(side_effect=answer)), patch(f"{SEARCH}.plain.fetch", new=fetch):
        return await search.find(_OREGON, "Lane County", url, "run-1", _OCDID, MagicMock())


@pytest.mark.asyncio
async def test_a_url_the_model_names_is_kept_as_its_final_url_when_the_page_is_the_charter():
    fetch = AsyncMock(return_value=_html(_FINAL, CHARTER_TEXT))

    answer = await _run([{"charter_urls": [_REDIRECT], "none_found": False}], fetch)

    assert (answer.found_by, answer.classification, answer.charter_urls, answer.general_law_urls) == (
        FoundBy.SEARCH, "county", [_FINAL], [_STATUTE]
    )
    fetch.assert_awaited_once_with(_REDIRECT)


@pytest.mark.asyncio
async def test_a_refused_or_wrong_url_falls_through_to_the_crawl():
    home = _html("https://www.lanecountyor.gov", '<a href="/charter">County Charter</a>')
    charter = _html("https://www.lanecountyor.gov/charter", CHARTER_TEXT)

    async def fetch(url):
        if url == _REDIRECT:
            raise RefusedByHost(url, 403)
        if url == "https://www.lanecountyor.gov/other":
            return _html(url, "A page that says charter once about Lane County.")
        return {home.url: home, charter.url: charter}.get(url)

    with patch(f"{SEARCH}.crawl.crawl", wraps=search.crawl.crawl) as crawled:
        answer = await _run([{"charter_urls": [_REDIRECT, "https://www.lanecountyor.gov/other"]}], AsyncMock(side_effect=fetch))

    crawled.assert_awaited_once()
    assert answer.charter_urls == [charter.url]
    assert answer.tried == [
        TriedUrl(url=_REDIRECT, reason=TriedReason.REFUSED),
        TriedUrl(url="https://www.lanecountyor.gov/other", reason=TriedReason.NOT_A_CHARTER),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [RuntimeError("All Gemini model fallbacks failed."), ValueError("Failed to parse JSON")])
async def test_a_model_that_fails_or_answers_no_json_is_a_miss_not_the_runs_end(failure: Exception):
    home = _html("https://www.lanecountyor.gov", '<a href="/charter">County Charter</a>')
    charter = _html("https://www.lanecountyor.gov/charter", CHARTER_TEXT)
    fetch = AsyncMock(side_effect=lambda url: {home.url: home, charter.url: charter}.get(url))

    answer = await _run(failure, fetch)

    assert answer.charter_urls == [charter.url]


@pytest.mark.asyncio
async def test_with_nothing_confirmed_and_no_site_only_the_statutes_remain():
    answer = await _run([{"charter_urls": []}], AsyncMock(), url=None)

    assert (answer.charter_urls, answer.general_law_urls, answer.tried) == ([], [_STATUTE], [])


@pytest.mark.asyncio
async def test_a_site_crawled_without_a_charter_is_among_the_urls_tried():
    home = _html("https://www.lanecountyor.gov", '<a href="/agendas">Agendas</a>')
    fetch = AsyncMock(side_effect=lambda url: {home.url: home}.get(url))

    answer = await _run([{"charter_urls": []}], fetch)

    assert (answer.charter_urls, answer.tried) == ([], [TriedUrl(url="https://www.lanecountyor.gov", reason=TriedReason.SITE_CRAWLED)])
