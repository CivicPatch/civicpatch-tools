"""A state's memberships, one row each — who holds which seat, and who used to.

Membership-grained. Closed rows are the point: git renders the live roster only, this keeps
history, so a former officeholder stays visible.

`person_name` rides along beside `person_id`. It is functionally dependent on the id, so it
multiplies nothing and the grain still holds — without it the tab is a wall of uuids.

Pure. Everything becomes text: a cell has no other type.
"""

from datetime import datetime, timezone

# Order is the contract: a tab written under one order and read under another transposes.
HEADERS = [
    "jurisdiction_ocdid",
    # The join back to Live[People][XX], and its label so a reader need not follow it.
    "person_id",
    "person_name",
    "post_id",
    # Composed, not stored — 148 dropped `posts.label`. Its inputs are the next two columns.
    "post_label",
    "post_role_id",
    "post_division_ocdid",
    "membership_id",
    "membership_label",
    # The source's dates; `first_seen_at` below is ours.
    "membership_start_date",
    "membership_end_date",
    "membership_first_seen_at",
    "membership_last_seen_at",
    # Empty means they still hold it. No `is_open`: that is this column with a NOT on it.
    "membership_closed_at",
    # Verbatim. `designations` is absent: it is `parse_label` run over these.
    "membership_source_labels",
]

_LIST_SEPARATOR = " | "


def _text(value) -> str:
    return "" if value is None else str(value)


def _joined(values: list | None) -> str:
    return _LIST_SEPARATOR.join(_text(value) for value in values or [])


def _timestamp(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).isoformat()


def to_row(membership: dict) -> list[str]:
    """Keys in match `HEADERS` one for one — `list_for_state` aliases its columns to these."""
    return [
        _text(membership.get("jurisdiction_ocdid")),
        _text(membership.get("person_id")),
        _text(membership.get("person_name")),
        _text(membership.get("post_id")),
        _text(membership.get("post_label")),
        _text(membership.get("post_role_id")),
        _text(membership.get("post_division_ocdid")),
        _text(membership.get("membership_id")),
        _text(membership.get("membership_label")),
        _text(membership.get("membership_start_date")),
        _text(membership.get("membership_end_date")),
        _timestamp(membership.get("membership_first_seen_at")),
        _timestamp(membership.get("membership_last_seen_at")),
        _timestamp(membership.get("membership_closed_at")),
        _joined(membership.get("membership_source_labels")),
    ]


def to_rows(memberships: list[dict]) -> list[list[str]]:
    return [to_row(membership) for membership in memberships]
