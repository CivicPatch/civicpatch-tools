"""A link into a code on eCode360 becomes the print page of the law wanted. Pages made up from the
shapes the site answered: a contents tree as JSON, a print page with a dated header."""

import json

import pytest
from runners.pipeline01_governing_law_collector import converters
from runners.pipeline01_governing_law_collector.finders import crawl, ecode360
from runners.pipeline01_governing_law_collector.schemas import FetchedPage, LawKind, LawTarget

pytestmark = pytest.mark.unit

_TARGET = LawTarget(kind=LawKind.CHARTER, description="municipal or county charter", terms=["Charter"], skip_words=["school"])
_TOC = {
    "guid": "AL4334",
    "children": [
        {"title": "Charter", "guid": "111", "children": [{"title": "Charter", "guid": "222", "children": [{"title": "NAME", "guid": "3"}, {"title": "COUNCIL", "guid": "4"}]}]},
        {"title": "Title 1 General Provisions", "guid": "555", "children": []},
    ],
}
_LAW = "<p>Section 1. Title. This enactment may be referred to as the Albany charter.</p>" * 10
_PRINT_URL = "https://ecode360.com/print/AL4334?guid=222"
_PRINT = f'<html><body class="ecodePrint"><main id="text"><div id="content"><h1 class="printHeader">City of Albany, OR<div>Wednesday, November 4, 2026</div></h1><h2 class="title chapterTitle">Title CHA. Charter</h2><div class="chapter_content content">{_LAW}</div></div></main></body></html>'


def _page(url: str, body: str | bytes, content_type: str = "text/html") -> FetchedPage:
    return FetchedPage(url=url, content_type=content_type, body=body.encode() if isinstance(body, str) else body, by_browser=False)


def _site(pages: dict[str, FetchedPage]):
    asked: list[str] = []

    async def fetch(url: str):
        asked.append(url)
        return pages.get(url)

    return fetch, asked


_SITE = {"https://ecode360.com/toc/AL4334": _page("https://ecode360.com/toc/AL4334", json.dumps(_TOC), "application/json"), _PRINT_URL: _page(_PRINT_URL, _PRINT)}


@pytest.mark.parametrize(
    "url,body",
    [("https://ecode360.com/AL4334", "<html><body></body></html>"), ("https://ecode360.com/49585565", '<html><body class="responsive contentPage CPC AL4334"></body></html>')],
    ids=["contents page", "any page, by its body class"],
)
def test_the_codes_id_comes_from_the_url_or_the_body(url: str, body: str):
    assert ecode360.code_of(_page(url, body)) == "AL4334"


def test_the_law_is_the_part_naming_the_target_and_a_division_of_one_prints_as_that_one():
    assert ecode360.law_guid(_TOC, _TARGET) == "222"


def test_a_code_without_the_law_has_no_guid():
    assert ecode360.law_guid({"children": [{"title": "Title 1 General Provisions", "guid": "555"}]}, _TARGET) is None


@pytest.mark.asyncio
async def test_a_link_into_the_code_resolves_to_the_laws_print_page():
    fetch, _ = _site(_SITE)

    page = await ecode360.resolved(_page("https://ecode360.com/AL4334", "<html></html>"), _TARGET, fetch)

    assert page.url == _PRINT_URL


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["https://www.lanecountyor.gov/charter", _PRINT_URL], ids=["another host", "already the print page"])
async def test_other_pages_ask_nothing_more(url: str):
    fetch, asked = _site(_SITE)
    page = _page(url, "<html></html>")

    assert await ecode360.resolved(page, _TARGET, fetch) is page
    assert asked == []


@pytest.mark.asyncio
async def test_a_contents_tree_that_cannot_be_read_leaves_the_page_as_it_came():
    fetch, _ = _site({"https://ecode360.com/toc/AL4334": _page("https://ecode360.com/toc/AL4334", "not json")})
    page = _page("https://ecode360.com/AL4334", "<html></html>")

    assert await ecode360.resolved(page, _TARGET, fetch) is page


def test_the_print_pages_text_leaves_out_its_dated_header():
    markdown = converters.to_markdown(_page(_PRINT_URL, _PRINT))

    assert "referred to as the Albany charter" in markdown
    assert "November 4, 2026" not in markdown


@pytest.mark.asyncio
async def test_the_crawl_keeps_the_print_page_of_a_charter_linked_from_a_home_page():
    site = "https://www.cityofalbany.net"
    home = _page(site, '<html><body><a href="https://ecode360.com/AL4334">City Charter</a></body></html>')
    contents = _page("https://ecode360.com/AL4334", "<html></html>")
    fetch, _ = _site({site: home, contents.url: contents, **_SITE})

    async def is_law(markdown: str, _url: str) -> bool:
        return "Albany charter" in markdown

    assert [page.url for page in (await crawl.crawl(site, [], _TARGET, is_law, fetch)).found] == [_PRINT_URL]
