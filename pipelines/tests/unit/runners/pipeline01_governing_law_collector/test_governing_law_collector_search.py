"""The search for a target: Gemini's urls are starting points of one crawl with the place's site."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from runners.pipeline01_governing_law_collector.fetchers import RefusedByHost, plain
from runners.pipeline01_governing_law_collector.finders import search
from runners.pipeline01_governing_law_collector.schemas import FetchedPage, LawKind, LawTarget, LawUrl, TriedReason, TriedUrl

pytestmark = pytest.mark.unit

SEARCH = "runners.pipeline01_governing_law_collector.finders.search"
FETCHERS = "runners.pipeline01_governing_law_collector.fetchers"
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


def _kept(found) -> list[tuple[str, LawKind]]:
    return [(law_url.url, law_url.kind) for law_url in found.law_urls]


async def _run(answer, fetch, url: str | None = "https://www.lanecountyor.gov", target=_TARGET, page_test=_is_charter_page):
    # The browser a 403 goes to meets the same answers as the plain fetch.
    with patch(f"{SEARCH}.gemini.run_prompt", new=AsyncMock(side_effect=answer)), patch(f"{SEARCH}.plain.fetch", new=fetch), patch(
        f"{FETCHERS}.browser.fetch", new=fetch
    ):
        return await search.find(target, page_test, "Lane County", url, "run-1", _OCDID, MagicMock())


@pytest.mark.asyncio
async def test_a_url_the_model_names_is_kept_as_its_final_url_when_the_page_is_the_charter():
    fetch = AsyncMock(side_effect=lambda url: _html(_FINAL, CHARTER_TEXT) if url == _REDIRECT else None)

    found = await _run([{"urls": [_REDIRECT]}], fetch)

    assert _kept(found) == [(_FINAL, LawKind.CHARTER)]


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
    assert _kept(found) == [(charter.url, LawKind.CHARTER)]
    assert found.tried == [
        TriedUrl(url=_REDIRECT, reason=TriedReason.REFUSED),
        TriedUrl(url="https://www.lanecountyor.gov/other", reason=TriedReason.NOT_THE_TARGET),
    ]


@pytest.mark.asyncio
async def test_a_host_that_challenges_the_crawl_is_among_the_urls_tried():
    async def fetch(url):
        if url == "https://www.lanecountyor.gov":
            raise RefusedByHost(url, 403, challenged=True)
        return None

    found = await _run([{"urls": []}], AsyncMock(side_effect=fetch))

    assert TriedUrl(url="https://www.lanecountyor.gov", reason=TriedReason.CHALLENGED) in found.tried


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [RuntimeError("All Gemini model fallbacks failed."), ValueError("Failed to parse JSON")])
async def test_a_model_that_fails_or_answers_no_json_is_a_miss_not_the_runs_end(failure: Exception):
    home = _html("https://www.lanecountyor.gov", '<a href="/charter">County Charter</a>')
    charter = _html("https://www.lanecountyor.gov/charter", CHARTER_TEXT)
    fetch = AsyncMock(side_effect=lambda url: {home.url: home, charter.url: charter}.get(url))

    found = await _run(failure, fetch)

    assert _kept(found) == [(charter.url, LawKind.CHARTER)]


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

    assert _kept(found) == [(page.url, LawKind.CODE)]
    fetched = [call.args[0] for call in fetch.await_args_list]
    assert fetched.index(page.url) < fetched.index("https://www.lanecountyor.gov/charter")


@pytest.mark.asyncio
async def test_a_site_crawled_without_a_charter_is_among_the_urls_tried():
    home = _html("https://www.lanecountyor.gov", '<a href="/agendas">Agendas</a>')
    fetch = AsyncMock(side_effect=lambda url: {home.url: home}.get(url))

    found = await _run([{"urls": []}], fetch)

    assert (found.law_urls, found.tried) == ([], [TriedUrl(url="https://www.lanecountyor.gov", reason=TriedReason.SITE_CRAWLED)])


@pytest.mark.asyncio
async def test_a_starting_point_is_checked_once_though_the_site_links_it_too():
    home = _html("https://www.lanecountyor.gov", f'<a href="{_FINAL}">County Charter</a>')
    tested: list[str] = []

    async def page_test(markdown: str, url: str) -> bool:
        tested.append(url)
        return await _is_charter_page(markdown, url)

    await _run([{"urls": [_FINAL]}], AsyncMock(side_effect={home.url: home, _FINAL: _html(_FINAL, CHARTER_TEXT)}.get), page_test=page_test)

    assert tested.count(_FINAL) == 1


@pytest.mark.asyncio
async def test_a_starting_points_links_naming_the_target_are_followed():
    index = _html("https://www.lanecountyor.gov/laws", '<a href="/charter">County Charter</a> <a href="/parks">Parks</a>')
    charter = _html("https://www.lanecountyor.gov/charter", CHARTER_TEXT)
    fetch = AsyncMock(side_effect={index.url: index, charter.url: charter}.get)

    found = await _run([{"urls": [index.url]}], fetch, url=None)

    assert _kept(found) == [(charter.url, LawKind.CHARTER)]
    assert "https://www.lanecountyor.gov/parks" not in [call.args[0] for call in fetch.await_args_list]


@pytest.mark.asyncio
async def test_with_no_site_the_host_of_what_the_model_named_is_crawled_from_its_home():
    named = "https://www.lanecountyor.gov/made-up-but-real-page"
    home = _html("https://www.lanecountyor.gov", '<a href="/charter">County Charter</a>')
    charter = _html("https://www.lanecountyor.gov/charter", CHARTER_TEXT)
    pages = {named: _html(named, "a page about the county"), home.url: home, charter.url: charter}

    found = await _run([{"urls": [named]}], AsyncMock(side_effect=pages.get), url=None)

    assert _kept(found) == [(charter.url, LawKind.CHARTER)]
    assert found.tried == [TriedUrl(url=named, reason=TriedReason.NOT_THE_TARGET)]


@pytest.mark.asyncio
async def test_with_no_site_a_publishers_host_does_not_stand_for_the_place():
    named = "https://library.municode.com/or/lane/codes/code_of_ordinances"
    fetch = AsyncMock(side_effect={named: _html(named, "a code's contents")}.get)

    await _run([{"urls": [named]}], fetch, url=None)

    assert [call.args[0] for call in fetch.await_args_list] == [named]


@pytest.mark.asyncio
async def test_the_home_page_named_as_a_starting_point_still_has_its_links_walked():
    home = _html("https://www.lanecountyor.gov", '<a href="/charter">County Charter</a>')
    charter = _html("https://www.lanecountyor.gov/charter", CHARTER_TEXT)

    found = await _run([{"urls": [home.url]}], AsyncMock(side_effect={home.url: home, charter.url: charter}.get))

    assert _kept(found) == [(charter.url, LawKind.CHARTER)]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure,reason", [(plain.OffLimits("x"), TriedReason.OFF_LIMITS), (httpx.ConnectError("x"), TriedReason.FAILED)])
async def test_a_named_url_that_cannot_be_read_says_why_but_a_crawled_one_does_not(failure: Exception, reason: TriedReason):
    named = "https://www.lanecountyor.gov/named"
    home = _html("https://www.lanecountyor.gov", '<a href="/charter">County Charter</a>')

    async def fetch(url):
        if url == named or url.endswith("/charter"):
            raise failure
        return {home.url: home}.get(url)

    found = await _run([{"urls": [named]}], AsyncMock(side_effect=fetch))

    assert found.tried == [TriedUrl(url=named, reason=reason), TriedUrl(url=home.url, reason=TriedReason.SITE_CRAWLED)]


@pytest.mark.asyncio
async def test_a_kept_url_carries_the_text_the_page_test_read():
    fetch = AsyncMock(side_effect=lambda url: _html(_FINAL, CHARTER_TEXT) if url == _REDIRECT else None)

    found = await _run([{"urls": [_REDIRECT]}], fetch)

    assert CHARTER_TEXT[:40] in (found.law_urls[0].markdown or "")
