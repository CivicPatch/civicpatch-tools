from enum import StrEnum


class JobStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    RESOLVED = "RESOLVED"


class PullRequestStatus(StrEnum):
    DEFAULT = "DEFAULT"
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class RequestStatus(StrEnum):
    DEFAULT = "DEFAULT"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
