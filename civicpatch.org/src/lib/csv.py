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
