from enum import StrEnum


class NavigationFailureReason(StrEnum):
    # Network Layer (Browser-level issues)
    NET_TIMEOUT = "navigation_failure_net_timeout"
    NET_DNS_FAILURE = "navigation_failure_net_dns_failure"
    NET_CONNECTION_REFUSED = "navigation_failure_net_connection_refused"
    NET_ABORTED = "navigation_failure_net_aborted"
    
    # HTTP Layer (Server-level responses)
    HTTP_403 = "navigation_failure_http_403"
    HTTP_429 = "navigation_failure_http_429"
    HTTP_5XX = "navigation_failure_http_5xx"
    
    # Fallback
    UNKNOWN = "navigation_failure_unknown"


# Failures that say "not right now" rather than "not ever". A refused connection, a dead DNS
# record or a 403 will read the same on a second attempt, so those stay terminal.
RETRYABLE_FAILURE_REASONS = frozenset(
    {
        NavigationFailureReason.NET_TIMEOUT,
        NavigationFailureReason.NET_ABORTED,
        NavigationFailureReason.HTTP_429,
        NavigationFailureReason.HTTP_5XX,
    }
)


class NavigationError(Exception):
    def __init__(self, url: str, reason: NavigationFailureReason, source: str):
        super().__init__(f"Failed to load page: {reason} ({url})")
        self.reason = reason
        self.source = source
