from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from shared.utils.statuses import ChangeLogType


class FieldChange(BaseModel):
    field: str
    before: Any | None = None
    after: Any | None = None


class PersonChangePayload(BaseModel):
    person_id: str
    person_name: str
    fields: list[FieldChange]


class PersonChange(BaseModel):
    type: ChangeLogType
    payload: PersonChangePayload


class ChangeLogBucket(StrEnum):
    QUARANTINE = "quarantine"  # changes authored by default-role users — reviewed for spam/profanity
    ACTIVITY = "activity"  # changes authored by trusted users (contributors and up)


class ChangeLogEntry(BaseModel):
    id: str
    type: ChangeLogType
    jurisdiction_ocdid: str | None
    jurisdiction_name: str | None
    jurisdiction_path: str | None = None
    request_id: str | None
    # Raw JSONB payload — shape varies by type. Kept as a dict so the wire
    # contract doesn't break when new types are added; humans read `summary`,
    # specialized renderers (e.g. person field-diff expander) can still dig in.
    changes: dict[str, Any] | None
    author_name: str | None
    author_role: str | None
    created_at: datetime
    summary: str
