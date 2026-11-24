import pytest
from runners.pipeline03_people_collector.schemas import Link, LinkFrontier, LinkStatus
from runners.pipeline03_people_collector.transitions.main import _all_failed_error_type
from runners.pipeline03_people_collector.steps.step_02_crawl_page.step_02a_scrape_page.scrape_exceptions import NavigationFailureReason
from shared.utils.statuses import PipelineIssueType, PipelineRunErrorType


def _frontier(*links: Link) -> LinkFrontier:
    from shared.utils.url_utils import canonical_url
    return LinkFrontier(links={canonical_url(l.url): l for l in links})


def _error_link(failure_reason=None, url="https://example.com") -> Link:
    return Link(url=url, status=LinkStatus.ERROR.value, failure_reason=failure_reason)


@pytest.mark.unit
def test_all_navigation_errors_returns_domain_navigation_error():
    frontier = _frontier(
        _error_link(NavigationFailureReason.NET_TIMEOUT, "https://example.com/a"),
        _error_link(NavigationFailureReason.NET_TIMEOUT, "https://example.com/b"),
    )
    assert _all_failed_error_type(frontier) == PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR


@pytest.mark.unit
def test_mixed_navigation_reasons_returns_domain_navigation_error():
    frontier = _frontier(
        _error_link(NavigationFailureReason.NET_TIMEOUT, "https://example.com/a"),
        _error_link(NavigationFailureReason.NET_DNS_FAILURE, "https://example.com/b"),
    )
    assert _all_failed_error_type(frontier) == PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR


@pytest.mark.unit
def test_http_403_returns_domain_navigation_error():
    frontier = _frontier(_error_link(NavigationFailureReason.HTTP_403))
    assert _all_failed_error_type(frontier) == PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR


@pytest.mark.unit
def test_no_failure_reason_returns_domain_inactive():
    frontier = _frontier(_error_link(failure_reason=None))
    assert _all_failed_error_type(frontier) == PipelineRunErrorType.DOMAIN_INACTIVE


@pytest.mark.unit
def test_no_error_links_returns_domain_inactive():
    frontier = _frontier(Link(url="https://example.com", status=LinkStatus.PREPROCESSED_NO_CONTENT.value))
    assert _all_failed_error_type(frontier) == PipelineRunErrorType.DOMAIN_INACTIVE


@pytest.mark.unit
def test_single_navigation_error_returns_domain_navigation_error():
    frontier = _frontier(_error_link(NavigationFailureReason.NET_TIMEOUT))
    assert _all_failed_error_type(frontier) == PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR


@pytest.mark.unit
def test_every_page_kept_out_by_robots_txt_is_source_blocked():
    frontier = _frontier(
        _error_link(NavigationFailureReason.DISALLOWED_BY_ROBOTS, "https://example.com/a"),
        _error_link(NavigationFailureReason.DISALLOWED_BY_ROBOTS, "https://example.com/b"),
    )
    assert _all_failed_error_type(frontier) == PipelineIssueType.SOURCE_BLOCKED


@pytest.mark.unit
def test_some_pages_kept_out_by_robots_txt_among_other_failures_is_a_navigation_error():
    frontier = _frontier(
        _error_link(NavigationFailureReason.DISALLOWED_BY_ROBOTS, "https://example.com/a"),
        _error_link(NavigationFailureReason.NET_TIMEOUT, "https://example.com/b"),
    )
    assert _all_failed_error_type(frontier) == PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR
