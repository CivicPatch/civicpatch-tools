"""The plain fetcher never reaches a url that is not a public web address, on the first hop or
any redirect hop: not http, no dotted host, or a bare IP address. It keeps to robots.txt and a pace.
A publisher's 403 goes to the browser; every other refusal stands."""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from patchright.async_api import Error as BrowserError
from pytest_httpx import HTTPXMock
from runners.pipeline01_governing_law_collector import fetchers
from runners.pipeline01_governing_law_collector.fetchers import browser, plain
from runners.pipeline01_governing_law_collector.schemas import FetchedPage

pytestmark = pytest.mark.unit

_CHARTER = "https://www.lanecountyor.gov/charter"
_ROBOTS = "https://www.lanecountyor.gov/robots.txt"


@pytest.fixture(autouse=True)
def _fresh_host_state():
    plain._robots_by_origin.clear()
    plain._next_request_by_host.clear()


def _no_robots(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=re.compile(r".*/robots\.txt$"), status_code=404, is_optional=True, is_reusable=True)


def _asked(httpx_mock: HTTPXMock) -> list[str]:
    return [str(request.url) for request in httpx_mock.get_requests() if not str(request.url).endswith(plain.ROBOTS_PATH)]


@pytest.mark.parametrize(
    "url,public",
    [
        (_CHARTER, True),
        ("https://counsel.bentoncountyor.gov/charter.pdf", True),
        ("http://localhost/charter", False),
        ("http://civicpatch-org-db:5432/", False),
        ("http://10.0.0.5/charter", False),
        ("http://169.254.169.254/latest/meta-data", False),
        ("http://[::1]/charter", False),
        ("file:///etc/passwd", False),
    ],
)
def test_only_an_http_url_with_a_dotted_hostname_is_public(url: str, public: bool):
    assert plain.is_public_web_url(url) == public


@pytest.mark.asyncio
async def test_an_off_limits_url_is_refused_before_any_request_is_sent(httpx_mock: HTTPXMock):
    with pytest.raises(plain.OffLimits):
        await plain.fetch("http://10.0.0.5/charter")

    assert httpx_mock.get_requests() == []


@pytest.mark.asyncio
async def test_a_redirect_to_an_off_limits_url_is_refused_at_that_hop(httpx_mock: HTTPXMock):
    _no_robots(httpx_mock)
    httpx_mock.add_response(url=_CHARTER, status_code=302, headers={"Location": "http://10.0.0.5/charter"})

    with pytest.raises(plain.OffLimits):
        await plain.fetch(_CHARTER)

    assert _asked(httpx_mock) == [_CHARTER]


@pytest.mark.asyncio
async def test_a_redirect_to_a_public_url_is_followed_and_the_final_url_kept(httpx_mock: HTTPXMock):
    _no_robots(httpx_mock)
    final = "https://www.lanecountyor.gov/files/charter.pdf"
    httpx_mock.add_response(url=_CHARTER, status_code=302, headers={"Location": final})
    httpx_mock.add_response(url=final, content=b"%PDF-", headers={"Content-Type": "application/pdf"})

    page = await plain.fetch(_CHARTER)

    assert (page.url, page.content_type, page.body) == (final, "application/pdf", b"%PDF-")


@pytest.mark.asyncio
async def test_a_url_robots_txt_disallows_is_never_requested(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=_ROBOTS, text="User-agent: CivicPatchBot\nDisallow: /charter\n")

    with pytest.raises(plain.DisallowedByRobots):
        await plain.fetch(_CHARTER)

    assert _asked(httpx_mock) == []


@pytest.mark.asyncio
async def test_rules_for_other_bots_do_not_apply_and_are_read_once_per_host(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=_ROBOTS, text="User-agent: GPTBot\nDisallow: /\n")
    httpx_mock.add_response(url=_CHARTER, text="law", is_reusable=True)

    with patch.object(plain.asyncio, "sleep", new=AsyncMock()):
        await plain.fetch(_CHARTER)
        await plain.fetch(_CHARTER)

    assert sum(str(request.url) == _ROBOTS for request in httpx_mock.get_requests()) == 1


@pytest.mark.asyncio
async def test_a_second_request_to_a_host_waits_its_turn_and_the_crawl_delay_is_kept(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=_ROBOTS, text="User-agent: *\nCrawl-delay: 5\n")
    httpx_mock.add_response(url=_CHARTER, text="law", is_reusable=True)

    with patch.object(plain.asyncio, "sleep", new=AsyncMock()) as slept:
        await plain.fetch(_CHARTER)
        await plain.fetch(_CHARTER)

    slept.assert_awaited_once()
    assert 4 < slept.await_args.args[0] <= 5


@pytest.mark.asyncio
async def test_a_cloudflare_challenge_is_a_refusal_marked_as_a_challenge(httpx_mock: HTTPXMock):
    _no_robots(httpx_mock)
    httpx_mock.add_response(url=_CHARTER, status_code=403, headers={plain.CHALLENGE_HEADER: plain.CHALLENGE_VALUE})

    with pytest.raises(plain.RefusedByHost) as refused:
        await plain.fetch(_CHARTER)

    assert refused.value.challenged is True


_PUBLISHER = "https://codelibrary.amlegal.com/codes/unionor/latest/overview"
_BROWSER_PAGE = FetchedPage(url=_PUBLISHER, content_type="text/html", body=b"law", by_browser=True)


@pytest.mark.asyncio
async def test_a_publishers_403_goes_to_the_browser_once(httpx_mock: HTTPXMock):
    _no_robots(httpx_mock)
    httpx_mock.add_response(url=_PUBLISHER, status_code=403)

    with patch.object(fetchers.browser, "fetch", new=AsyncMock(return_value=_BROWSER_PAGE)) as by_browser:
        page = await fetchers.fetch_plain_first(_PUBLISHER)

    by_browser.assert_awaited_once_with(_PUBLISHER)
    assert page == _BROWSER_PAGE


@pytest.mark.asyncio
async def test_a_redirect_to_a_publishers_403_goes_to_the_browser_at_the_publishers_url(httpx_mock: HTTPXMock):
    _no_robots(httpx_mock)
    httpx_mock.add_response(url=_CHARTER, status_code=302, headers={"Location": _PUBLISHER})
    httpx_mock.add_response(url=_PUBLISHER, status_code=403)

    with patch.object(fetchers.browser, "fetch", new=AsyncMock(return_value=_BROWSER_PAGE)) as by_browser:
        await fetchers.fetch_plain_first(_CHARTER)

    by_browser.assert_awaited_once_with(_PUBLISHER)


@pytest.mark.asyncio
@pytest.mark.parametrize("url,status", [(_CHARTER, 403), (_PUBLISHER, 429)])
async def test_a_places_own_403_and_a_publishers_429_stay_refused(httpx_mock: HTTPXMock, url: str, status: int):
    _no_robots(httpx_mock)
    httpx_mock.add_response(url=url, status_code=status)

    with patch.object(fetchers.browser, "fetch", new=AsyncMock()) as by_browser, pytest.raises(plain.RefusedByHost):
        await fetchers.fetch_plain_first(url)

    by_browser.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_publisher_url_robots_txt_disallows_never_reaches_the_browser(httpx_mock: HTTPXMock):
    httpx_mock.add_response(url=re.compile(r".*/robots\.txt$"), text="User-agent: *\nDisallow: /\n")

    with patch.object(fetchers.browser, "fetch", new=AsyncMock()) as by_browser, pytest.raises(plain.DisallowedByRobots):
        await fetchers.fetch_plain_first(_PUBLISHER)

    by_browser.assert_not_awaited()


@pytest.mark.parametrize(
    "url,publisher",
    [
        ("https://library.municode.com/or/carlton", True),
        ("https://ashland.municipal.codes/Charter", True),
        ("https://www.ecode360.com/AL4334", True),
        ("https://notmunicode.com/or/carlton", False),
        ("https://www.lanecountyor.gov/municode.com", False),
    ],
)
def test_a_publisher_is_known_by_its_host(url: str, publisher: bool):
    assert fetchers.is_publisher(url) == publisher


def _loaded(status: int, first_title: str, last_title: str) -> browser.LoadedPage:
    return browser.LoadedPage(url=_PUBLISHER, status=status, first_title=first_title, last_title=last_title)


_CHALLENGE = browser.CHALLENGE_TITLE


@pytest.mark.parametrize(
    "loaded",
    [_loaded(200, "Union, OR", "Union, OR"), _loaded(403, _CHALLENGE, "Union, OR")],
)
def test_a_read_page_or_a_cleared_challenge_is_no_failure(loaded: browser.LoadedPage):
    assert browser._failure(_PUBLISHER, loaded) is None


@pytest.mark.parametrize(
    "loaded,challenged",
    [
        (_loaded(403, _CHALLENGE, _CHALLENGE), True),
        (_loaded(200, "Ashland", _CHALLENGE), True),
        (_loaded(403, "Forbidden", "Forbidden"), False),
        (_loaded(429, "Slow down", "Slow down"), False),
    ],
)
def test_a_challenge_left_standing_or_a_refusal_is_a_refusal(loaded: browser.LoadedPage, challenged: bool):
    failure = browser._failure(_PUBLISHER, loaded)

    assert isinstance(failure, plain.RefusedByHost)
    assert failure.challenged is challenged


def test_any_other_error_status_is_a_failed_fetch():
    assert isinstance(browser._failure(_PUBLISHER, _loaded(404, "Not found", "Not found")), httpx.TransportError)


@pytest.mark.asyncio
async def test_loading_waits_out_a_challenge_and_keeps_the_first_answer():
    titles = iter([_CHALLENGE, _CHALLENGE, "Union, OR"])
    last = {"title": _CHALLENGE}

    async def title():
        last["title"] = next(titles, last["title"])
        return last["title"]

    page = MagicMock(url=_PUBLISHER, goto=AsyncMock(return_value=MagicMock(status=403)), title=title, wait_for_timeout=AsyncMock())

    loaded = await browser._load(page, _PUBLISHER)

    assert loaded == _loaded(403, _CHALLENGE, "Union, OR")


@pytest.mark.asyncio
async def test_a_first_url_robots_txt_disallows_opens_no_browser():
    with patch.object(plain, "obey_host", new=AsyncMock(side_effect=plain.DisallowedByRobots(_PUBLISHER))), patch.object(browser, "async_playwright") as playwright:
        with pytest.raises(plain.DisallowedByRobots):
            await browser.fetch(_PUBLISHER)

    playwright.assert_not_called()


def _route(url: str, *, navigation: bool = True) -> MagicMock:
    request = MagicMock(url=url)
    request.is_navigation_request.return_value = navigation
    request.frame.parent_frame = None
    return MagicMock(request=request, continue_=AsyncMock(), abort=AsyncMock())


_HOP = "https://elsewhere.example.org/charter"


def _obeying_except_the_hop(failure: Exception | None) -> AsyncMock:
    async def obey_host(url: str) -> None:
        if url == _HOP and failure:
            raise failure

    return AsyncMock(side_effect=obey_host)


@pytest.mark.asyncio
async def test_a_redirect_robots_txt_disallows_is_aborted_and_recorded():
    hop, stopped = _route(_HOP), []

    with patch.object(plain, "obey_host", new=_obeying_except_the_hop(plain.DisallowedByRobots(_HOP))):
        await browser._guard(_PUBLISHER, stopped, hop)

    hop.abort.assert_awaited_once()
    assert isinstance(stopped[0], plain.DisallowedByRobots)


@pytest.mark.asyncio
async def test_an_allowed_redirect_goes_on_and_records_nothing():
    hop, stopped = _route(_HOP), []

    with patch.object(plain, "obey_host", new=_obeying_except_the_hop(None)):
        await browser._guard(_PUBLISHER, stopped, hop)

    hop.continue_.assert_awaited_once()
    assert stopped == []


@pytest.mark.asyncio
async def test_a_private_address_a_page_asks_for_is_aborted_without_blaming_the_page():
    private, stopped = _route("http://10.0.0.5/secret", navigation=False), []

    await browser._guard(_PUBLISHER, stopped, private)

    private.abort.assert_awaited_once()
    assert stopped == []


@pytest.mark.asyncio
async def test_the_first_urls_challenge_reload_takes_no_second_turn():
    with patch.object(plain, "obey_host", new=AsyncMock()) as obeyed:
        assert await browser._blocked_hop(_PUBLISHER, _PUBLISHER) is None

    obeyed.assert_not_awaited()


def _playwright_whose_navigation_passes(route: MagicMock) -> MagicMock:
    """The first navigation runs this route through the fetch's guard, then the browser gives up."""
    context = MagicMock(route=AsyncMock())

    async def goto(_url, **_options):
        await context.route.await_args.args[1](route)
        raise BrowserError("navigation aborted")

    context.new_page = AsyncMock(return_value=MagicMock(goto=goto))
    opened = MagicMock(new_context=AsyncMock(return_value=context), close=AsyncMock())
    playwright = MagicMock()
    playwright.chromium.launch = AsyncMock(return_value=opened)
    manager = MagicMock()
    manager.__aenter__.return_value = playwright
    manager.__aexit__.return_value = False
    return manager


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "hop_failure,expected",
    [(plain.DisallowedByRobots(_HOP), plain.DisallowedByRobots), (None, httpx.TransportError)],
)
async def test_a_browser_failure_is_reported_as_the_blocked_hop_or_else_as_a_failed_fetch(hop_failure, expected):
    manager = _playwright_whose_navigation_passes(_route(_HOP))

    with patch.object(browser, "async_playwright", return_value=manager), patch.object(plain, "obey_host", new=_obeying_except_the_hop(hop_failure)):
        with pytest.raises(expected):
            await browser.fetch(_PUBLISHER)
