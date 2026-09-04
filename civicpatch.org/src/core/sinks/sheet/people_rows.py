"""The people we hold in a state, one row each.

Person-grained: this is the tab a curator scans for a near-miss *name*, where a person repeated
once per seat is noise. Who holds what is `membership_rows`.

Pure. Everything becomes text: a cell has no other type.
"""

from datetime import datetime, timezone

# Order is the contract: a tab written under one order and read under another transposes.
HEADERS = [
    "jurisdiction_ocdid",
    "person_id",
    "person_name",
    "person_other_names",
    "person_emails",
    "person_phones",
    "person_urls",
    "person_image",
    "person_source_urls",
    "person_updated_at",
]

_LIST_SEPARATOR = " | "


def _text(value) -> str:
    return "" if value is None else str(value)


def _joined(values: list | None) -> str:
    return _LIST_SEPARATOR.join(_text(value) for value in values or [])


def _timestamp(value: datetime | None) -> str:
    """UTC ISO 8601, as `PERSON_JSON` renders `updated_at` in SQL."""
    if value is None:
        return ""
    return value.astimezone(timezone.utc).isoformat()


def _image(person: dict) -> str:
    """The CDN copy once promoted, the original until then."""
    return _text(person.get("person_cdn_image") or person.get("person_image"))


def to_row(person: dict) -> list[str]:
    """Keys in match `HEADERS` one for one — `stream_for_state` aliases its columns to these."""
    return [
        _text(person.get("jurisdiction_ocdid")),
        _text(person.get("person_id")),
        _text(person.get("person_name")),
        _joined(person.get("person_other_names")),
        _joined(person.get("person_emails")),
        _joined(person.get("person_phones")),
        _joined(person.get("person_urls")),
        _image(person),
        _joined(person.get("person_source_urls")),
        _timestamp(person.get("person_updated_at")),
    ]


def to_rows(people: list[dict]) -> list[list[str]]:
    return [to_row(person) for person in people]
