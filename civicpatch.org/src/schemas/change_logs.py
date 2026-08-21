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


class PostChangePayload(BaseModel):
    """`change_logs` has no `post_id` column, so the anchor rides in the payload — the same
    way person events carry `person_name`. `label` is what a reader recognises a post by."""

    post_id: str
    role_id: str
    division_ocdid: str
    label: str | None = None
    fields: list[FieldChange] = []


class MembershipChangePayload(BaseModel):
    """`person_name`, `role_id` and `label` are carried because ids do not render — the same
    reason person events carry `person_name`. `moved_from` is the post vacated, absent on a
    first assignment."""

    membership_id: str
    person_id: str
    person_name: str
    post_id: str
    role_id: str
    label: str | None = None
    moved_from: str | None = None


class JurisdictionChangePayload(BaseModel):
    jurisdiction_ocdid: str
    jurisdiction_name: str
    fields: list[FieldChange]


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
    pull_request_url: str | None = None
    # Raw JSONB payload — shape varies by type. Kept as a dict so the wire
    # contract doesn't break when new types are added; humans read `summary`,
    # specialized renderers (e.g. person field-diff expander) can still dig in.
    changes: dict[str, Any] | None
    author_name: str | None
    author_role: str | None
    created_at: datetime
    summary: str
