from dataclasses import dataclass


@dataclass
class OpenDataCommitItem:
    """One jurisdiction inside a batch commit."""

    file_path: str
    # Every changeset this file's content lands, each stamped with the commit url. Plural for
    # the sweep covers a window of change rather than one publish.
    changeset_ids: list[str]
    jurisdiction_ocdid: str


@dataclass
class OpenDataBatchCommitRequest:
    batch_id: str
    items: list[OpenDataCommitItem]
    commit_message: str
