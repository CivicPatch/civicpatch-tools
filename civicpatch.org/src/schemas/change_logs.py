from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from shared.utils.statuses import ChangeLogType, DismissalReason


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


class DismissalPayload(BaseModel):
    """Why a changeset was dismissed, recorded on its `close_review` log.

    Stored rather than derived on read: `status` and `resolved_by_user_id` are both mutable, so
    reconstructing this later could give a past event a different meaning than it had.
    """

    reason: DismissalReason


class PostChangePayload(BaseModel):
    """`change_logs` has no `post_id` column, so the anchor rides in the payload — the same
    way person events carry `person_name`. `label` is what a reader recognises a post by."""

    post_id: str
    role_id: str
    division_ocdid: str
    label: str | None = None
    fields: list[FieldChange] = []


# The seat a membership points at, named once: written in `database.memberships` and read back
# in `core.change_logs` to tell a move from a first assignment.
MEMBERSHIP_POST_FIELD = "post_id"


class MembershipChangePayload(BaseModel):
    """`person_name`, `role_id` and `label` are carried because ids do not render — the same
    reason person events carry `person_name`.

    `fields` records what moved, as on every other payload: `post_id` for a move, `label` for a
    rename. A first assignment is the one whose `post_id` change has no `before`.
    """

    membership_id: str
    person_id: str
    person_name: str
    post_id: str
    role_id: str
    label: str | None = None
    fields: list[FieldChange] = []


class AssertionChangePayload(BaseModel):
    """Assertions are current state and can be overwritten, so the log is what keeps the
    superseded value. `sources` rides along because it is the only record of why."""

    entity_type: str
    entity_id: str
    field_path: str
    kind: str
    value: Any = None
    sources: list[dict] = []


class JurisdictionChangePayload(BaseModel):
    jurisdiction_ocdid: str
    jurisdiction_name: str
    fields: list[FieldChange]


class RosterChange(BaseModel):
    """One roster change under a changeset's timeline entry.

    `name` is what the change is about, `fields` is what moved. The per-type payloads name that
    subject differently — `person_name` on person and membership events, `label` (falling back
    to `role_id`) on post ones — and resolving it here is what lets a reader treat every change
    alike.

    A membership move is a `post` field change like any other, rather than its own key: the
    verb is already in `type`, so a second signal for it only invites the two to disagree.

    `detail` is the seat a membership names. Without it the only renderable thing left for an
    assignment is the field name `post_id` or a raw uuid, because a membership's subject is the
    person and the post's label would otherwise be dropped on the way out.
    """

    type: ChangeLogType
    created_at: datetime
    name: str
    detail: str | None = None
    fields: list[FieldChange] = []


class ChangeLogBucket(StrEnum):
    QUARANTINE = "quarantine"  # changes authored by default-role users — reviewed for spam/profanity
    ACTIVITY = "activity"  # changes authored by trusted users (contributors and up)


class ChangeLogEntry(BaseModel):
    id: str
    type: ChangeLogType
    jurisdiction_ocdid: str | None
    jurisdiction_name: str | None
    jurisdiction_path: str | None = None
    changeset_id: str | None
    pull_request_url: str | None = None
    # Raw JSONB payload — shape varies by type. Kept as a dict so the wire
    # contract doesn't break when new types are added; humans read `summary`,
    # specialized renderers (e.g. person field-diff expander) can still dig in.
    changes: dict[str, Any] | None
    author_name: str | None
    author_role: str | None
    created_at: datetime
    summary: str
