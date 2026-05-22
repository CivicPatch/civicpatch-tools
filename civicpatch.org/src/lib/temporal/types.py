from dataclasses import dataclass


@dataclass
class MergeRequest:
    pull_request_number: str
    request_id: str
    approved_by: str | None
    user_id: str
    merge_key: str
