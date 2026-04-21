from enum import StrEnum


class NavigationFailureReason(StrEnum):
    NAVIGATION_TIMEOUT = "navigation_timeout"
    DNS_FAILURE = "dns_failure"
    CONNECTION_REFUSED = "connection_refused"
    UNKNOWN = "unknown"


class NavigationError(Exception):
    def __init__(self, url: str, reason: NavigationFailureReason, source: str):
        super().__init__(f"Failed to load page: {reason} ({url})")
        self.reason = reason
        self.source = source
