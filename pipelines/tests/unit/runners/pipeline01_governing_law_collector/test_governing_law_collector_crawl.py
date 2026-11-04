"""The site crawl over a made-up county site: home > board > charter page > PDF, a sitemap that
names the charter, links off-site and to subdomains, and a budget."""

import pytest
from runners.pipeline01_governing_law_collector.finders import crawl
from runners.pipeline01_governing_law_collector.schemas import FetchedPage, LawKind, LawTarget

pytestmark = pytest.mark.unit

SITE = "https://www.example-county.gov"
TARGET = LawTarget(kind=LawKind.CHARTER, description="municipal or county charter", terms=["Charter"], skip_words=["school"])
_CLAUSE = "Section {n}. The board of county commissioners shall consist of five county commissioners. "
CHARTER_TEXT = "HOME RULE CHARTER FOR EXAMPLE COUNTY " + "".join(_CLAUSE.format(n=n) for n in range(1, 61))


async def _is_charter_page(markdown: str, _url: str) -> bool:
    return "HOME RULE CHARTER" in markdown


def _html(url: str, body: str) -> FetchedPage:
    return FetchedPage(url=url, content_type="text/html", body=f"<html><body>{body}</body></html>".encode(), by_browser=False)


def _text(url: str, body: str, content_type: str = "text/plain") -> FetchedPage:
    return FetchedPage(url=url, content_type=content_type, body=body.encode(), by_browser=False)


def _site(pages: dict[str, FetchedPage]):
    fetched: list[str] = []

    async def fetch(url: str):
        fetched.append(url)
        return pages.get(url)

    return fetch, fetched


_HOME = _html(SITE, '<a href="/departments/board">Board of Commissioners</a> <a href="https://other.example.org/x">Partner</a> <a href="https://counsel.example-county.gov/">County Counsel</a>')
_BOARD = _html(f"{SITE}/departments/board", '<a href="/departments/board/charter">County Charter</a> <a href="/departments/board/agendas">Agendas</a>')
_CHARTER_PAGE = _html(f"{SITE}/departments/board/charter", '<p>Read the charter.</p> <a href="/files/charter.pdf">Home Rule Charter (PDF)</a>')
_CHARTER_FILE = _html(f"{SITE}/files/charter.pdf", f"<article>{CHARTER_TEXT}</article>")


@pytest.mark.asyncio
async def test_a_charter_three_hops_from_home_is_found_through_charter_named_links():
    fetch, fetched = _site({SITE: _HOME, _BOARD.url: _BOARD, _CHARTER_PAGE.url: _CHARTER_PAGE, _CHARTER_FILE.url: _CHARTER_FILE})

    found = await crawl.crawl(SITE, TARGET, _is_charter_page, fetch)

    assert found == [_CHARTER_FILE.url]
    assert f"{SITE}/departments/board/agendas" not in fetched


@pytest.mark.asyncio
async def test_a_sitemap_entry_naming_the_charter_is_read_first_and_its_links_followed():
    sitemap = _text(f"{SITE}/sitemap.xml", f"<urlset><url><loc>{SITE}/departments/board/charter</loc></url></urlset>", "application/xml")
    fetch, fetched = _site({sitemap.url: sitemap, _CHARTER_PAGE.url: _CHARTER_PAGE, _CHARTER_FILE.url: _CHARTER_FILE})

    found = await crawl.crawl(SITE, TARGET, _is_charter_page, fetch)

    assert found == [_CHARTER_FILE.url]
    assert fetched.index(_CHARTER_PAGE.url) < fetched.index(SITE)


@pytest.mark.asyncio
async def test_every_page_of_a_charter_is_found_and_the_links_of_each_followed():
    contents = _html(f"{SITE}/charter", f'<article>{CHARTER_TEXT}</article> <a href="/charter/chapter-2">Charter chapter 2</a>')
    chapter = _html(f"{SITE}/charter/chapter-2", f"<article>{CHARTER_TEXT}</article>")
    home = _html(SITE, '<a href="/charter">City Charter</a>')
    fetch, _ = _site({SITE: home, contents.url: contents, chapter.url: chapter})

    assert await crawl.crawl(SITE, TARGET, _is_charter_page, fetch) == [contents.url, chapter.url]


@pytest.mark.asyncio
async def test_a_sitemap_index_is_recursed():
    index = _text(f"{SITE}/sitemap.xml", f"<sitemapindex><sitemap><loc>{SITE}/pages.xml</loc></sitemap></sitemapindex>", "application/xml")
    pages = _text(f"{SITE}/pages.xml", f"<urlset><url><loc>{_CHARTER_FILE.url}</loc></url></urlset>", "application/xml")
    fetch, _ = _site({index.url: index, pages.url: pages, _CHARTER_FILE.url: _CHARTER_FILE})

    assert await crawl.crawl(SITE, TARGET, _is_charter_page, fetch) == [_CHARTER_FILE.url]


@pytest.mark.asyncio
async def test_the_crawl_stops_at_its_budget():
    many = {f"{SITE}/page{n}": _html(f"{SITE}/page{n}", f'<a href="/page{n + 1}">Next</a>') for n in range(200)}
    home = _html(SITE, "".join(f'<a href="/page{n}">Page {n}</a>' for n in range(200)))
    fetch, fetched = _site({SITE: home, **many})

    assert await crawl.crawl(SITE, TARGET, _is_charter_page, fetch) == []
    assert len(fetched) == crawl.MAX_PAGES


@pytest.mark.asyncio
async def test_a_link_only_its_anchor_text_calls_a_charter_is_read_ahead_of_a_long_menu():
    charter = _html(f"{SITE}/DocumentCenter/View/123", f"<article>{CHARTER_TEXT}</article>")
    menu = "".join(f'<a href="/page{n}">Page {n}</a>' for n in range(200))
    home = _html(SITE, f'{menu} <a href="/DocumentCenter/View/123">City Charter</a>')
    fetch, fetched = _site({SITE: home, charter.url: charter})

    assert await crawl.crawl(SITE, TARGET, _is_charter_page, fetch) == [charter.url]
    assert fetched.index(charter.url) < fetched.index(f"{SITE}/page0")


def _link_urls(html: bytes, site: str = SITE, *, named_only: bool) -> list[str]:
    return [link.url for link in crawl.links(html, site, site, TARGET, named_only=named_only)]


def test_the_first_hop_keeps_the_site_and_its_subdomains_and_drops_other_hosts():
    assert _link_urls(_HOME.body, named_only=False) == [
        f"{SITE}/departments/board",
        "https://counsel.example-county.gov/",
    ]


def test_deeper_hops_keep_only_charter_named_links_on_any_host():
    html = b'<a href="https://cdn.example.net/charter.pdf">Charter</a> <a href="/agendas">Agendas</a> <a href="/charter-school">Charter School</a>'

    assert _link_urls(html, named_only=True) == ["https://cdn.example.net/charter.pdf"]


def test_charter_named_links_come_first():
    html = b'<a href="/a">Agendas</a> <a href="/county-charter">Charter and Code</a>'

    assert _link_urls(html, named_only=False) == [f"{SITE}/county-charter", f"{SITE}/a"]


def test_a_translation_proxys_copy_of_the_site_is_never_followed():
    html = b'<a href="https://www-example-gov.translate.goog/charter?_x_tr_sl=en">County Charter</a> <a href="/charter">County Charter</a>'

    assert _link_urls(html, named_only=True) == [f"{SITE}/charter"]


def test_a_place_with_school_in_its_host_keeps_its_links():
    site = "https://www.schoolcraftcounty.net"
    html = b'<a href="https://www.schoolcraftcounty.net/board">Board</a> <a href="https://www.schoolcraftcounty.net/districts">School districts</a>'

    assert _link_urls(html, site, named_only=False) == [f"{site}/board"]


def test_a_robots_file_names_its_sitemaps():
    assert crawl.sitemap_urls(b"User-agent: *\nSitemap: https://www.example-county.gov/sitemap_index.xml\n") == [
        "https://www.example-county.gov/sitemap_index.xml"
    ]
