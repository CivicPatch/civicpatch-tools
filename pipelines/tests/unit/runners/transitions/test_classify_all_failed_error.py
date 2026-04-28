import pytest
from runners.people_collector.schemas import Link, LinkStatus
from runners.people_collector.transitions.main import _classify_all_failed_error
from runners.people_collector.steps.step_02_scrape_page.scrape_exceptions import NavigationFailureReason
from shared.utils.statuses import PipelineRunErrorType


def _error_link(failure_reason=None):
    return Link(url="https://example.com", status=LinkStatus.ERROR.value, failure_reason=failure_reason)


@pytest.mark.unit
def test_all_navigation_errors_returns_domain_navigation_error():
    links = [
        _error_link(NavigationFailureReason.NET_TIMEOUT),
        _error_link(NavigationFailureReason.NET_TIMEOUT),
    ]
    assert _classify_all_failed_error(links) == PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR


@pytest.mark.unit
def test_mixed_navigation_reasons_returns_domain_navigation_error():
    links = [
        _error_link(NavigationFailureReason.NET_TIMEOUT),
        _error_link(NavigationFailureReason.NET_DNS_FAILURE),
    ]
    assert _classify_all_failed_error(links) == PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR


@pytest.mark.unit
def test_http_403_returns_domain_navigation_error():
    links = [_error_link(NavigationFailureReason.HTTP_403)]
    assert _classify_all_failed_error(links) == PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR


@pytest.mark.unit
def test_no_failure_reason_returns_domain_inactive():
    links = [_error_link(failure_reason=None)]
    assert _classify_all_failed_error(links) == PipelineRunErrorType.DOMAIN_INACTIVE


@pytest.mark.unit
def test_no_error_links_returns_domain_inactive():
    links = [Link(url="https://example.com", status=LinkStatus.PREPROCESSED_NO_CONTENT.value)]
    assert _classify_all_failed_error(links) == PipelineRunErrorType.DOMAIN_INACTIVE


@pytest.mark.unit
def test_single_navigation_error_returns_domain_navigation_error():
    links = [_error_link(NavigationFailureReason.NET_TIMEOUT)]
    assert _classify_all_failed_error(links) == PipelineRunErrorType.DOMAIN_NAVIGATION_ERROR