"""What a sink is about to write, as one string.

Hashes the rendered rows rather than the bytes a sink sends. Parquet encoding is not
byte-stable — compression, metadata timestamps and row-group boundaries vary between runs — so
a hash of the encoded file would differ every time and the gate would never match.

Line-per-row so that a sink streaming its rows and one holding them all in a list agree on the
answer. The sheet streams (a state is up to 20 MB and states sync concurrently); open-data
renders one YAML string and uses `hash_text` directly.
"""

import hashlib
import json


def hash_text(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


def row_line(row: list[str]) -> str:
    """One row's canonical form. The trailing newline is what makes a field boundary real:
    without it `["ab", "c"]` and `["a", "bc"]` could agree, and a real edit would skip its write.
    """
    return json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n"


def hash_rows(rows: list[list[str]]) -> str:
    """Position is the identity: every query feeding a sink already has an ORDER BY."""
    return hash_text("".join(row_line(row) for row in rows))
