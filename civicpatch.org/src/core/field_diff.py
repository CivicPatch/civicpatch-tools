"""Which fields differ between two person records — the card's diff.

`name`, `other_names`, `start_date`, `end_date`, `emails`, `phones`, `urls`, and nothing else:
the reviewer's field set, pinned by `person-diff-cases.json` for both the client and the server.
The projection diff (`core/projection/diff.py`) compares a wider set for R6; the two answer
different questions, so this is not a second copy of it.
"""

# Mirrors the compared entries of `FIELD_SCHEMA` in frontend/components/fields/field-schema.ts,
# in its order. Photo and source urls are `diff: false`; the office is a membership.
_SCALAR_FIELDS = ("name", "start_date", "end_date")
_COMPARED_FIELDS = ("name", "other_names", "start_date", "end_date", "emails", "phones", "urls")


def _scalar(value: object) -> str:
    return "" if value is None else str(value).strip()


def _as_set(values: list | None) -> set[str]:
    return {str(value).strip().lower() for value in values or []}


def changed_fields(published: dict, proposed: dict) -> list[str]:
    """Same rule as the card: scalars by trimmed text, lists as case-folded sets."""
    changed = []
    for field in _COMPARED_FIELDS:
        if field in _SCALAR_FIELDS:
            differs = _scalar(published.get(field)) != _scalar(proposed.get(field))
        else:
            differs = _as_set(published.get(field)) != _as_set(proposed.get(field))
        if differs:
            changed.append(field)
    return changed
