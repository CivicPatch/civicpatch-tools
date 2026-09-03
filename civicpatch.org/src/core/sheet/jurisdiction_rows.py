"""Every jurisdiction we hold — the roster tab's dropdown source.

Column A is the raw ocdid: it is what the importer wants, and Sheets filters a dropdown by
substring, so typing `sherborn` still finds it.

One flat tab, not one per state, because a validation rule points at a single contiguous range.
That is what lets `Entry[Roster]` accept any state.
"""

HEADERS = [
    "jurisdiction_ocdid",
    "name",
    "url",
    "population",
    "level",
]


def _text(value) -> str:
    return "" if value is None else str(value)


def to_row(jurisdiction: dict) -> list[str]:
    return [_text(jurisdiction.get(column)) for column in HEADERS]


def to_rows(jurisdictions: list[dict]) -> list[list[str]]:
    return [to_row(jurisdiction) for jurisdiction in jurisdictions]
