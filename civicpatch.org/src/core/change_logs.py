"""Pure change-log helpers: the field diff a payload carries, and the formatter that turns a
(type, changes) pair into a human-readable summary string for the activity feed."""

from collections.abc import Mapping
from datetime import datetime

from schemas.change_logs import MEMBERSHIP_POST_FIELD, FieldChange, RosterChange
from shared.utils.statuses import ChangeLogType


def field_changes(
    before: Mapping[str, object], after: Mapping[str, object]
) -> list[FieldChange]:
    """Only the keys `before` names — the caller decides what was in scope for the edit.

    `object`, not `Any`: the values are compared and passed through, never inspected.
    """
    return [
        FieldChange(field=field, before=before[field], after=after[field])
        for field in before
        if before[field] != after[field]
    ]


def _moved_seat(changes: Mapping) -> bool:
    """Whether an assignment vacated a seat. A first assignment has no `before`."""
    return any(
        field.get("field") == MEMBERSHIP_POST_FIELD and field.get("before")
        for field in changes.get("fields") or []
    )


def _post_name(changes: Mapping) -> str:
    """What a reader recognises a seat by. Same fallback as the summary formatter below."""
    return changes.get("label") or changes.get("role_id") or "post"


def _subject(type_: ChangeLogType, changes: Mapping) -> str:
    if type_ == ChangeLogType.EDIT_JURISDICTION:
        # The place itself is the subject — there is no person or seat to name.
        return changes.get("jurisdiction_name") or "jurisdiction"
    if type_ == ChangeLogType.ASSERT_FIELD:
        # An assertion payload stores only ids, so the reader resolves `entity_name` and puts
        # it here on the way out. The type is the fallback when the entity is gone — better a
        # bare "person" than a uuid nobody can read.
        return changes.get("entity_name") or changes.get("entity_type") or "record"
    return changes.get("person_name") or _post_name(changes)


def roster_change(
    type_: ChangeLogType, created_at: datetime, changes: Mapping
) -> RosterChange:
    """One `change_logs` row as a timeline entry.

    The payload families name their subject differently and record movement differently, so
    this is the single place that knows which shape is which.
    """
    if type_ == ChangeLogType.ASSERT_FIELD:
        fields = [FieldChange(field=changes["field_path"], after=changes.get("value"))]
    else:
        fields = [FieldChange(**field) for field in changes.get("fields") or []]

    return RosterChange(
        type=type_,
        created_at=created_at,
        name=_subject(type_, changes),
        # Only a membership has a second subject worth naming: its seat. Everything else is
        # already fully described by `name` plus the fields that moved.
        detail=(
            _post_name(changes)
            if type_ == ChangeLogType.ASSIGN_MEMBERSHIP
            else None
        ),
        fields=fields,
    )


def _alias_summary(payload: dict) -> str:
    added = payload.get("aliases_added") or []
    removed = payload.get("aliases_removed") or []
    parts = []
    if added:
        parts.append(f"+{len(added)} alias{'es' if len(added) != 1 else ''}")
    if removed:
        parts.append(f"-{len(removed)} alias{'es' if len(removed) != 1 else ''}")
    return f" ({', '.join(parts)})" if parts else ""


def _reorder_summary(payload: dict) -> str:
    """Describe a reorder. Prefers the explicit `moved` list (the roles the user
    actually dragged) and names them. Falls back, for older entries without it,
    to the role that shifted furthest — since before/after alone can't tell an
    intentional move from a one-slot side-effect shift."""
    moved = payload.get("moved") or []
    if moved:
        shown = ", ".join(moved[:3])
        extra = len(moved) - 3
        suffix = f" (+{extra} more)" if extra > 0 else ""
        return f"Reordered roles: moved {shown}{suffix}"

    before = payload.get("before") or []
    after = payload.get("after") or []
    movers = [r for r in after if r in before and before.index(r) != after.index(r)]
    if not movers:
        return "Reordered roles"
    primary = max(movers, key=lambda r: abs(before.index(r) - after.index(r)))
    pos = after.index(primary)
    where = "to the top" if pos == 0 else f"below '{after[pos - 1]}'"
    return f"Reordered roles: '{primary}' moved {where}"


def summarize_change_log(type_: str, changes: dict | None) -> str:
    """Pure: render a one-line summary for an activity-feed row.
    Unknown types fall back to the raw type — never raises."""
    c = changes or {}

    # ── Person events ───────────────────────────────────────────────────
    if type_ in ("add_person", "edit_person", "delete_person"):
        verb = {"add_person": "Added", "edit_person": "Edited", "delete_person": "Deleted"}[type_]
        name = c.get("person_name") or "person"
        fields = c.get("fields") or []
        field_part = f" ({len(fields)} field{'s' if len(fields) != 1 else ''})" if fields else ""
        return f"{verb} {name}{field_part}"

    if type_ == "edit_jurisdiction":
        return "Edited jurisdiction"

    if type_ in ("merge_review", "close_review"):
        return "Merged review" if type_ == "merge_review" else "Closed review"

    if type_ == "reorder_roles":
        return _reorder_summary(c)

    # ── Post events ─────────────────────────────────────────────────────
    # The label is what a person named the post; the role id is all there is without one.
    post = c.get("label") or c.get("role_id") or "post"

    if type_ == "assign_membership":
        who = c.get("person_name") or "someone"
        # A move is the fact worth reading: it means a closed row was left behind.
        if _moved_seat(c):
            return f"Moved {who} to '{post}'"
        return f"Assigned {who} to '{post}'"

    if type_ in ("add_post", "edit_post", "delete_post"):
        verb = {"add_post": "Added", "edit_post": "Edited", "delete_post": "Removed"}[type_]
        fields = c.get("fields") or []
        field_part = f" ({', '.join(f['field'] for f in fields)})" if fields else ""
        return f"{verb} post '{post}'{field_part}"

    # ── Role taxonomy events ────────────────────────────────────────────
    role = c.get("role", "?")

    if type_ == "add_role":
        return f"Added role '{role}'{_alias_summary(c)}"
    if type_ == "edit_role":
        return f"Edited role '{role}'{_alias_summary(c)}"
    if type_ == "delete_role":
        return f"Removed role '{role}'"
    # Retired event types — kept so existing change_log rows still render.
    if type_ == "exclude_role":
        return f"Excluded role '{role}'"
    if type_ == "include_role":
        return f"Included '{role}' as role"

    return type_
