from dataclasses import dataclass
from enum import StrEnum


class CommitSource(StrEnum):
    """Which database table the file's content is rendered from.

    The two open-data paths mean different things, so they render from different places:
    the unreviewed copy is the scrape exactly as submitted, while the reviewed copy is the
    jurisdiction's live roster — which may include people from earlier scrapes.
    """

    SCRAPE = "scrape"    # one scrape's proposal, derived from its sightings
    ROSTER = "roster"    # people WHERE status='active' — what is currently live


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
    source: CommitSource = CommitSource.SCRAPE
    # Removed once the write above succeeds — promotion is a move, and deleting first would
    # lose the data if the write then failed.
    delete_path: str | None = None
    delete_message: str | None = None


@dataclass
class OpenDataCommitItem:
    """One jurisdiction inside a batch commit."""

    file_path: str
    request_id: str
    jurisdiction_ocdid: str


@dataclass
class OpenDataBatchCommitRequest:
    """Every jurisdiction a bulk publish made live, as one commit.

    A file at a time would leave forty commits for one reviewer action, which is not what
    happened — they published once. `source` is absent because a batch is always a publish, so
    it always renders from the live roster.
    """

    batch_id: str
    items: list[OpenDataCommitItem]
    commit_message: str
