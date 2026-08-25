import pytest

from runners.people_collector.steps.step_02_scrape_page.browser import _failure_detail

# Shape of a real patchright navigation timeout: the reason, then a "Call log:" block.
TIMEOUT_ERROR = (
    "Page.goto: Timeout 15000ms exceeded.\n"
    "Call log:\n"
    '  - navigating to "https://example.com/mayor", waiting until "networkidle"\n'
)


@pytest.mark.unit
def test_timeout_wins_over_self_inflicted_abort():
    detail = _failure_detail("net::ERR_ABORTED", [TIMEOUT_ERROR] * 3)
    assert "TIMEOUT" in detail
    assert "ERR_ABORTED" not in detail


@pytest.mark.unit
def test_abort_survives_when_no_navigation_error_preceded_it():
    assert _failure_detail("net::ERR_ABORTED", []) == "NET::ERR_ABORTED"


@pytest.mark.unit
def test_non_abort_request_failure_wins_over_navigation_error():
    assert (
        _failure_detail("net::ERR_NAME_NOT_RESOLVED", [TIMEOUT_ERROR])
        == "NET::ERR_NAME_NOT_RESOLVED"
    )


# A fast 403/404 answers on the first attempt, so nothing is recorded either way — the caller
# needs an empty detail rather than a raised IndexError to reach its http_status branch.
@pytest.mark.unit
def test_http_error_response_yields_empty_detail():
    assert _failure_detail(None, []) == ""


@pytest.mark.unit
def test_call_log_block_is_dropped():
    assert (
        _failure_detail(None, [TIMEOUT_ERROR]) == "PAGE.GOTO: TIMEOUT 15000MS EXCEEDED."
    )
