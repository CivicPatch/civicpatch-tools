from dataclasses import dataclass


@dataclass
class MergeRequest:
    pull_request_number: str
    request_id: str
    approved_by: str | None
    user_id: str
    merge_key: str


@dataclass
class OpenDataCommitRequest:
    """What to write into open-data, by reference rather than by value.

    The content is deliberately absent: the activity renders it from the database on every
    attempt, so a retry converges on current truth instead of replaying bytes captured when
    the workflow started. It also keeps rosters out of Temporal's payload limits.
    """
    file_path: str
    request_id: str
    jurisdiction_ocdid: str
    commit_message: str
