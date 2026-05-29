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

    # ── Role taxonomy events ────────────────────────────────────────────
    role = c.get("role", "?")
    kind = c.get("kind", "canonical")
    label = "role" if kind == "canonical" else "exclusion"

    if type_ == "add_role":
        return f"Added {label} '{role}'{_alias_summary(c)}"
    if type_ == "edit_role":
        return f"Edited {label} '{role}'{_alias_summary(c)}"
    if type_ == "delete_role":
        return f"Removed {label} '{role}'"
    if type_ == "exclude_role":
        return f"Excluded role '{role}'"
    if type_ == "include_role":
        return f"Included exclusion '{role}' as role"

    return type_
