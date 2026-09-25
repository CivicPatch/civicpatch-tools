from datetime import datetime

from pydantic import BaseModel, Field


class RollbackCandidate(BaseModel):
    """One changeset in a user's recent history --- what a rollback screen lists.

    The unit is the changeset, not the claim (§17): one action is undone or it is not, and a
    changeset is the only thing that spans the facts one action filed. `jurisdiction_ocdid` rides
    along for display; `comment` is set on a rollback and null on everything else, which is how a
    list distinguishes an undo from the edit it undid.
    """

    changeset_id: str
    kind: str
    jurisdiction_ocdid: str
    jurisdiction_name: str
    comment: str | None
    published_at: datetime


class RollbackRequest(BaseModel):
    """Which of a user's changesets to roll back, and why.

    `comment` is required and non-empty: a rollback's content is only withdraws, so its reason
    cannot be reconstructed from what it holds the way every other changeset's can.
    """

    changeset_ids: list[str] = Field(min_length=1)
    comment: str = Field(min_length=1)
