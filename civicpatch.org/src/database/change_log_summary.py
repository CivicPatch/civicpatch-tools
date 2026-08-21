"""Pure formatter that turns a (type, changes) pair into a human-readable
summary string for the activity feed."""


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
        if c.get("moved_from"):
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
