from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from schemas.assertions import EntityType
from shared.utils.statuses import ChangeLogType


class FieldChange(BaseModel):
    field: str
    before: Any | None = None
    after: Any | None = None
    # Why somebody said so — "phoned the clerk, there really are five trustees". Only an
    # assertion carries one, and this is the single place it is recorded: `assertions` is
    # current state and gets overwritten, so the log is what keeps a superseded justification.
    sources: list[dict] = []


# The seat a membership points at, named once: written in `database.memberships` and read back
# in `core.change_logs` to tell a move from a first assignment.
MEMBERSHIP_POST_FIELD = "post_id"


class Change(BaseModel):
    entity_type: EntityType
    entity_id: str
    subject: str
    detail: str | None = None
    fields: list[FieldChange] = []


class PersonChange(BaseModel):
    """A typed change `people_diff` produces: which kind of event, and what it says."""

    type: ChangeLogType
    payload: Change


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


class ChangedJurisdiction(BaseModel):
    """One jurisdiction the feed says changed, what kinds of change reached it, and which
    changesets they belonged to.

    The types are carried so the open-data commit can name what it is mirroring — a sweep knows
    the jurisdiction changed but, without them, nothing about how.

    `changeset_ids` is what lets the sweep stamp `change_url`, which `promote_to_reviewed` used
    to do by holding the id itself. Plural because one commit legitimately covers several
    changesets' worth of change — the one-id-per-commit shape could not say that.
    """

    jurisdiction_ocdid: str
    change_types: list[str]
    changeset_ids: list[str] = []
