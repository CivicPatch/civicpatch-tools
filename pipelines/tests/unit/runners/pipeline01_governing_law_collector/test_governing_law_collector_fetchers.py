"""The plain fetcher never reaches a url that is not a public web address, on the first hop or
any redirect hop: not http, no dotted host, or a bare IP address."""

import pytest
from pytest_httpx import HTTPXMock
from runners.pipeline01_governing_law_collector.fetchers import plain

pytestmark = pytest.mark.unit

_CHARTER = "https://www.lanecountyor.gov/charter"


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
    httpx_mock.add_response(url=_CHARTER, status_code=302, headers={"Location": "http://10.0.0.5/charter"})

    with pytest.raises(plain.OffLimits):
        await plain.fetch(_CHARTER)

    assert [str(request.url) for request in httpx_mock.get_requests()] == [_CHARTER]


@pytest.mark.asyncio
async def test_a_redirect_to_a_public_url_is_followed_and_the_final_url_kept(httpx_mock: HTTPXMock):
    final = "https://www.lanecountyor.gov/files/charter.pdf"
    httpx_mock.add_response(url=_CHARTER, status_code=302, headers={"Location": final})
    httpx_mock.add_response(url=final, content=b"%PDF-", headers={"Content-Type": "application/pdf"})

    page = await plain.fetch(_CHARTER)

    assert (page.url, page.content_type, page.body) == (final, "application/pdf", b"%PDF-")
