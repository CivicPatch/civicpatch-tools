"""A link into a code on Municode becomes the page of the law searched for. Node ids and titles are
real: Carlton's CHCA, Washington County's CH and CH01, Newport's code with no charter part."""

from unittest.mock import AsyncMock

import pytest
from runners.pipeline01_governing_law_collector.finders import crawl, municode, publishers
from runners.pipeline01_governing_law_collector.schemas import FetchedPage, LawKind, LawTarget
from utils.page_links import PageLink

pytestmark = pytest.mark.unit

_TARGET = LawTarget(kind=LawKind.CHARTER, description="municipal charter", terms=["Charter"], skip_words=["school"])
_CODE = "https://library.municode.com/or/carlton/codes/code_of_ordinances"


def _node(node: str, text: str) -> PageLink:
    return PageLink(url=f"{_CODE}?nodeId={node}", text=text)


def _page(url: str, links: str = "") -> FetchedPage:
    return FetchedPage(url=url, content_type="text/html", body=f"<html><body>{links}</body></html>".encode(), by_browser=True)


def _anchors(*links: PageLink) -> str:
    return "".join(f'<a href="{link.url}">{link.text}</a>' for link in links)


@pytest.mark.parametrize(
    "links,node",
    [
        ([_node("SUHITA", "SUPPLEMENT HISTORY TABLE"), _node("CHCA", "CHARTER for the CITY OF CARLTON")], "CHCA"),
        ([_node("CH", "CHARTER"), _node("CH01", "Charter")], "CH01"),
        ([_node("CHTR", "CHARTER"), _node("CHCOTA", "CHARTER COMPARATIVE TABLE")], "CHTR"),
    ],
)
def test_the_law_is_the_first_part_naming_it_or_the_part_inside_that(links: list[PageLink], node: str):
    found = municode.law_link(links, _TARGET)

    assert found is not None and municode.node_of(found.url) == node


@pytest.mark.parametrize(
    "links",
    [
        [_node("TIT1GEPR", "TITLE I - GENERAL PROVISIONS")],
        [_node("CHSC", "Charter School Agreements")],
        [PageLink(url="https://library.municode.com/or", text="Oregon charter cities")],
    ],
)
def test_a_code_with_no_part_naming_the_law_has_no_link(links: list[PageLink]):
    assert municode.law_link(links, _TARGET) is None


@pytest.mark.asyncio
async def test_a_code_page_becomes_its_laws_page():
    charter = _page(f"{_CODE}?nodeId=CHCA", "the charter")
    fetch = AsyncMock(return_value=charter)

    found = await municode.resolved(_page(_CODE, _anchors(_node("CHCA", "CHARTER for the CITY OF CARLTON"))), _TARGET, fetch)

    fetch.assert_awaited_once_with(charter.url)
    assert found == charter


@pytest.mark.asyncio
async def test_the_laws_own_page_is_not_fetched_again():
    url = f"{_CODE}?nodeId=CHTR"
    page = _page(url, _anchors(PageLink(url=f"{url}#_CHTR", text="Skip to CHARTER"), _node("CHTR", "CHARTER")))
    fetch = AsyncMock()

    assert await municode.resolved(page, _TARGET, fetch) == page
    fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_code_page_stays_as_it_came_when_the_law_will_not_fetch_or_is_not_there():
    named = _page(_CODE, _anchors(_node("CHCA", "CHARTER")))
    unnamed = _page(_CODE, _anchors(_node("TIT1GEPR", "TITLE I")))

    assert await municode.resolved(named, _TARGET, AsyncMock(return_value=None)) == named
    assert await municode.resolved(unnamed, _TARGET, AsyncMock()) == unnamed


@pytest.mark.asyncio
async def test_another_hosts_page_stays_as_it_came():
    page = _page("https://www.carltonoregon.gov/code", _anchors(_node("CHCA", "CHARTER")))
    fetch = AsyncMock()

    assert await publishers.resolved(page, _TARGET, fetch) == page
    fetch.assert_not_awaited()


_SITE = "https://www.carltonoregon.gov"


@pytest.mark.parametrize("named_only", [False, True])
def test_a_link_into_a_publisher_is_kept_whatever_it_says_and_goes_first(named_only: bool):
    html = _anchors(PageLink(url=f"{_SITE}/parks", text="Parks"), PageLink(url=_CODE, text="Municipal Code")).encode()

    found = [link.url for link in crawl.links(html, _SITE, _SITE, _TARGET, named_only=named_only)]

    assert found[0] == _CODE


def test_a_publishers_own_links_are_left_to_its_handler():
    html = _anchors(_node("TIT1GEPR", "TITLE I"), _node("TIT2", "TITLE II")).encode()

    assert crawl.links(html, _CODE, _SITE, _TARGET, named_only=False) == []
