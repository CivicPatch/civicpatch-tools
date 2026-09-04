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


def roster_change(
    type_: ChangeLogType, created_at: datetime, changes: Mapping
) -> RosterChange:
    """One `change_logs` row as a timeline entry.

    Every entity payload carries its own subject now, so this no longer has to know which shape
    it is holding. It used to dispatch on `type_` to decide whether the name lived in
    `person_name`, `label`, `role_id` or `jurisdiction_name`.
    """
    return RosterChange(
        type=type_,
        created_at=created_at,
        name=changes.get("subject") or "record",
        detail=changes.get("detail"),
        fields=[FieldChange(**field) for field in changes.get("fields") or []],
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


# What each entity verb reads as. The payload no longer differs by type, so this is the only
# thing left that does — and it is a word, not a shape.
_VERBS: dict[str, str] = {
    "add_person": "Added",
    "edit_person": "Edited",
    "delete_person": "Deleted",
    "add_post": "Added post",
    "edit_post": "Edited post",
    "delete_post": "Removed post",
    "edit_jurisdiction": "Edited",
    "assert_field": "Asserted on",
}


def summarize_change_log(type_: str, changes: dict | None) -> str:
    """Pure: render a one-line summary for an activity-feed row.
    Unknown types fall back to the raw type — never raises."""
    c = changes or {}

    if type_ in ("publish_review", "dismiss_review"):
        return "Published review" if type_ == "publish_review" else "Dismissed review"

    if type_ == "reorder_roles":
        return _reorder_summary(c)

    # ── Entity events ───────────────────────────────────────────────────
    # One shape, so one renderer. This used to be six branches, each pulling the subject out of
    # a different key and counting or naming fields differently.
    if type_ == "assign_membership":
        who = c.get("subject") or "someone"
        seat = c.get("detail") or "post"
        # A move is the fact worth reading: it means a closed row was left behind.
        return f"{'Moved' if _moved_seat(c) else 'Assigned'} {who} to '{seat}'"

    if verb := _VERBS.get(type_):
        name = c.get("subject") or "record"
        fields = c.get("fields") or []
        field_part = (
            f" ({len(fields)} field{'s' if len(fields) != 1 else ''})" if fields else ""
        )
        return f"{verb} {name}{field_part}"

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
