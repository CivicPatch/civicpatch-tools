"""The search for a target: Gemini's urls confirmed by fetch, then the crawl, always."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from runners.pipeline01_governing_law_collector.fetchers import RefusedByHost
from runners.pipeline01_governing_law_collector.finders import search
from runners.pipeline01_governing_law_collector.schemas import FetchedPage, LawKind, LawTarget, LawUrl, TriedReason, TriedUrl

pytestmark = pytest.mark.unit

SEARCH = "runners.pipeline01_governing_law_collector.finders.search"
_OCDID = "ocd-jurisdiction/country:us/state:or/county:lane/government"
_TARGET = LawTarget(kind=LawKind.CHARTER, description="municipal or county charter", terms=["Charter", "Home Rule Charter"], skip_words=["school"])
_CLAUSE = "Section {n}. The board of county commissioners shall consist of five county commissioners. "
CHARTER_TEXT = "HOME RULE CHARTER FOR LANE COUNTY " + "".join(_CLAUSE.format(n=n) for n in range(1, 61))
_REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc"
_FINAL = "https://www.lanecountyor.gov/files/charter.pdf"


async def _is_charter_page(markdown: str, _url: str) -> bool:
    return "HOME RULE CHARTER" in markdown


def _html(url: str, body: str) -> FetchedPage:
    return FetchedPage(url=url, content_type="text/html", body=f"<html><body><article>{body}</article></body></html>".encode(), by_browser=False)


async def _run(answer, fetch, url: str | None = "https://www.lanecountyor.gov", target=_TARGET, page_test=_is_charter_page):
    with patch(f"{SEARCH}.gemini.run_prompt", new=AsyncMock(side_effect=answer)), patch(f"{SEARCH}.plain.fetch", new=fetch):
        return await search.find(target, page_test, "Lane County", url, "run-1", _OCDID, MagicMock())


@pytest.mark.asyncio
async def test_a_url_the_model_names_is_kept_as_its_final_url_when_the_page_is_the_charter():
    fetch = AsyncMock(side_effect=lambda url: _html(_FINAL, CHARTER_TEXT) if url == _REDIRECT else None)

    found = await _run([{"urls": [_REDIRECT]}], fetch)

    assert found.law_urls == [LawUrl(url=_FINAL, kind=LawKind.CHARTER)]


@pytest.mark.asyncio
async def test_a_confirmed_url_does_not_stop_the_crawl_and_a_url_found_twice_is_kept_once():
    amendment = _html("https://www.lanecountyor.gov/charter-amendment", CHARTER_TEXT)
    home = _html("https://www.lanecountyor.gov", f'<a href="/charter-amendment">Charter Amendment</a> <a href="{_FINAL}">County Charter</a>')
    pages = {_REDIRECT: _html(_FINAL, CHARTER_TEXT), _FINAL: _html(_FINAL, CHARTER_TEXT), home.url: home, amendment.url: amendment}

    found = await _run([{"urls": [_REDIRECT]}], AsyncMock(side_effect=pages.get))

    assert [law_url.url for law_url in found.law_urls] == [_FINAL, amendment.url]


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
        found = await _run([{"urls": [_REDIRECT, "https://www.lanecountyor.gov/other"]}], AsyncMock(side_effect=fetch))

    crawled.assert_awaited_once()
    assert found.law_urls == [LawUrl(url=charter.url, kind=LawKind.CHARTER)]
    assert found.tried == [
        TriedUrl(url=_REDIRECT, reason=TriedReason.REFUSED),
        TriedUrl(url="https://www.lanecountyor.gov/other", reason=TriedReason.NOT_THE_TARGET),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [RuntimeError("All Gemini model fallbacks failed."), ValueError("Failed to parse JSON")])
async def test_a_model_that_fails_or_answers_no_json_is_a_miss_not_the_runs_end(failure: Exception):
    home = _html("https://www.lanecountyor.gov", '<a href="/charter">County Charter</a>')
    charter = _html("https://www.lanecountyor.gov/charter", CHARTER_TEXT)
    fetch = AsyncMock(side_effect=lambda url: {home.url: home, charter.url: charter}.get(url))

    found = await _run(failure, fetch)

    assert found.law_urls == [LawUrl(url=charter.url, kind=LawKind.CHARTER)]


@pytest.mark.asyncio
async def test_with_nothing_confirmed_and_no_site_nothing_is_found():
    found = await _run([{"urls": []}], AsyncMock(), url=None)

    assert (found.law_urls, found.tried) == ([], [])


@pytest.mark.asyncio
async def test_a_target_with_no_terms_asks_no_model_and_crawls_nothing():
    no_terms = _TARGET.model_copy(update={"terms": []})
    with patch(f"{SEARCH}.gemini.run_prompt", new=AsyncMock()) as asked, patch(f"{SEARCH}.plain.fetch", new=AsyncMock()) as fetched:
        found = await search.find(no_terms, _is_charter_page, "Lane County", "https://www.lanecountyor.gov", "run-1", _OCDID, MagicMock())

    asked.assert_not_awaited()
    fetched.assert_not_awaited()
    assert (found.law_urls, found.tried) == ([], [])


@pytest.mark.asyncio
async def test_the_search_finds_whatever_kind_its_target_and_page_test_name():
    code = LawTarget(kind=LawKind.CODE, description="municipal code", terms=["Revised Code"])
    home = _html("https://www.lanecountyor.gov", '<a href="/charter">County Charter</a> <a href="/lc">Revised Code</a>')
    page = _html("https://www.lanecountyor.gov/lc", "the code")
    fetch = AsyncMock(side_effect=lambda url: {home.url: home, page.url: page}.get(url))

    async def is_the_code(markdown: str, _url: str) -> bool:
        return "the code" in markdown

    found = await _run([{"urls": []}], fetch, target=code, page_test=is_the_code)

    assert found.law_urls == [LawUrl(url=page.url, kind=LawKind.CODE)]
    fetched = [call.args[0] for call in fetch.await_args_list]
    assert fetched.index(page.url) < fetched.index("https://www.lanecountyor.gov/charter")


@pytest.mark.asyncio
async def test_a_site_crawled_without_a_charter_is_among_the_urls_tried():
    home = _html("https://www.lanecountyor.gov", '<a href="/agendas">Agendas</a>')
    fetch = AsyncMock(side_effect=lambda url: {home.url: home}.get(url))

    found = await _run([{"urls": []}], fetch)

    assert (found.law_urls, found.tried) == ([], [TriedUrl(url="https://www.lanecountyor.gov", reason=TriedReason.SITE_CRAWLED)])
