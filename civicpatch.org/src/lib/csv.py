import csv
import io

# How the entry sheet marks a column for the human reading its header; never part of the key.
REQUIRED_MARKER = "*"
READ_ONLY_MARKER = " (read-only)"


def column_key(header_text) -> str:
    """A header cell as the column it names: "Name*" and "published_other_names (read-only)"
    are `name` and `published_other_names`."""
    key = str(header_text or "").strip().lower()
    key = key.removesuffix(READ_ONLY_MARKER.strip()).strip()
    return key.rstrip(REQUIRED_MARKER).strip()


def rows_from_table(table: list[list]) -> list[dict]:
    """A header row and its data rows, as dicts keyed by the header. Shared by the CSV and
    Sheets readers, so one sheet cannot parse differently depending on how it was read.

    Headers go through `column_key` — a header row is typed by a human, and the entry sheet's
    markers are for the human reading it, not characters to match on.
    Short rows are padded, because Sheets omits trailing empty cells and a blank optional field
    is an empty value, not a missing column. A leading `'` is stripped: Sheets prefixes a value
    with it to force text formatting (e.g. keeping a leading `=` from being read as a formula).
    """
    if not table:
        return []
    header = [column_key(name) for name in table[0]]
    return [
        {
            key: _unsanitize(row[index] if index < len(row) else "")
            for index, key in enumerate(header)
            if key
        }
        for row in table[1:]
    ]


def parse_csv(text: str) -> list[dict]:
    """A CSV's data rows, keyed by its header.

    No validation here: this is `lib/`, so it turns bytes into rows and stops. What a row has to
    contain is `core.sheet_import`'s question.
    """
    return rows_from_table(list(csv.reader(io.StringIO(text))))


def _unsanitize(value) -> str:
    if not isinstance(value, str):
        return "" if value is None else str(value)
    return value[1:] if value[:1] == "'" else value
