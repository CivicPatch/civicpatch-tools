"""Every jurisdiction we hold — reference for whoever is filling in `Entry[Roster]` by hand.

Column A is the ocdid: it is what the importer wants, and it is what `Entry[Roster]`'s own
`jurisdiction_ocdid` column is filled in with. `geoid` trails as a reference column for cross
checking against a source that only supplies one.

One flat tab, not one per state, so any state's jurisdiction can be looked up in the same place.
"""

HEADERS = [
    "jurisdiction_ocdid",
    "name",
    "url",
    "population",
    "level",
    "geoid",
]


def _text(value) -> str:
    return "" if value is None else str(value)


def to_row(jurisdiction: dict) -> list[str]:
    return [_text(jurisdiction.get(column)) for column in HEADERS]


def to_rows(jurisdictions: list[dict]) -> list[list[str]]:
    return [to_row(jurisdiction) for jurisdiction in jurisdictions]
