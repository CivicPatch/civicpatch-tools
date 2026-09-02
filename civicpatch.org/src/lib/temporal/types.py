from dataclasses import dataclass


@dataclass
class OpenDataCommitRequest:
    """What to write into open-data, by reference rather than by value.

    The content is deliberately absent: the activity renders it from the database on every
    attempt, so a retry converges on current truth instead of replaying bytes captured when
    the workflow started. It also keeps rosters out of Temporal's payload limits.
    """
    file_path: str
    # None for an edit with no request row, which is every write that is not a publish.
    changeset_id: str | None
    jurisdiction_ocdid: str
    commit_message: str
    # Removed once the write above succeeds — promotion is a move, and deleting first would
    # lose the data if the write then failed.
    delete_path: str | None = None
    delete_message: str | None = None


@dataclass
class OpenDataCommitItem:
    """One jurisdiction inside a batch commit."""

    file_path: str
    changeset_id: str
    jurisdiction_ocdid: str


@dataclass
class OpenDataBatchCommitRequest:
    """Every jurisdiction a bulk publish made live, as one commit.

    A file at a time would leave forty commits for one reviewer action, which is not what
    happened — they published once.
    """

    batch_id: str
    items: list[OpenDataCommitItem]
    commit_message: str
