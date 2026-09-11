from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RollbackCandidate(BaseModel):
    """One assertion in a user's history — what a UI lists and checks boxes against.
    `jurisdiction_ocdid` rides along for display only; selecting and executing never requires
    picking one first. `status` is the assertion's `AssertionState` value ("active",
    "superseded", "withdrawn"); only "active" rows are real rollback candidates."""

    assertion_id: str
    entity_id: str
    entity_label: str
    field_path: str
    value: Any
    jurisdiction_ocdid: str
    status: str
    created_at: datetime


class RollbackRequest(BaseModel):
    """Which of a user's candidate assertions to roll back — always explicit, whether that's
    every id a listing returned ("select all") or a hand-picked subset."""

    assertion_ids: list[str] = Field(min_length=1)
    reason: str | None = None
