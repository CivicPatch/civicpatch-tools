from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import AliasChoices, BaseModel, Field

from shared.utils.statuses import ChangeLogType


class FieldChange(BaseModel):
    field: str
    from_: Any | None = Field(
        default=None,
        validation_alias=AliasChoices("from_", "from"),
        serialization_alias="from",
    )
    to: Any | None = None


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
    request_id: str | None
    changes: PersonChangePayload | None
    author_name: str | None
    author_role: str | None
    created_at: datetime
