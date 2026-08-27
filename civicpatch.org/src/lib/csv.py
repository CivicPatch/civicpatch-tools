import csv
import io
from typing import Generator, Iterable

# Characters that spreadsheet applications (Excel, Sheets) interpret as formula prefixes
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize(val: str) -> str:
    """Prevent CSV formula injection by prefixing dangerous values with a single quote."""
    if val and val[0] in _FORMULA_PREFIXES:
        return "'" + val
    return val


def rows_from_table(table: list[list]) -> list[dict]:
    """A header row and its data rows, as dicts keyed by the header. Shared by the CSV and
    Sheets readers, so one sheet cannot parse differently depending on how it was read.

    Headers are lowercased and stripped — a header row is typed by a human. Short rows are
    padded, because Sheets omits trailing empty cells and a blank optional field is an empty
    value, not a missing column. A leading `'` is stripped: that is `sanitize`'s guard, and
    Sheets applies the same escape.
    """
    if not table:
        return []
    header = [str(name or "").strip().lower() for name in table[0]]
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


def generate_csv(rows: Iterable[dict], fieldnames: list[str]) -> Generator[str, None, None]:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    yield buf.getvalue()

    for row in rows:
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames, lineterminator="\n")
        writer.writerow(row)
        yield buf.getvalue()
