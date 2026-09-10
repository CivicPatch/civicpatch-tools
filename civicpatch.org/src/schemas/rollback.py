from typing import Any

from pydantic import BaseModel, Field


class RollbackCandidate(BaseModel):
    """One assertion a user could roll back — what a UI lists and checks boxes against.
    `jurisdiction_ocdid` rides along for display only; selecting and executing never requires
    picking one first."""

    assertion_id: str
    entity_id: str
    entity_label: str
    field_path: str
    value: Any
    jurisdiction_ocdid: str


class RollbackRequest(BaseModel):
    """Which of a user's candidate assertions to roll back — always explicit, whether that's
    every id a listing returned ("select all") or a hand-picked subset."""

    assertion_ids: list[str] = Field(min_length=1)
    reason: str | None = None
