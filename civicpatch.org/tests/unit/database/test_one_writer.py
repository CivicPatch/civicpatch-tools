"""Only `database/projection.py` writes the projection (R5 of the projector plan).

`people`, `memberships`, `membership_roles`, `posts` and `organizations` are derived tables.
Once the fold rebuilds them (step 8), any other write is a patch the next rebuild silently
undoes, or a value the facts never said. The guard is a scan of the source tree rather than
a runtime check: a write that never runs in a test still has to be caught.

Writes still outside the writer are allow-listed by file and statement with the plan step
that deletes each, and the count has to match exactly: a new write fails, and a deleted write
fails until its entry goes, so the list cannot rot in either direction.
"""

import os
import re

import pytest

_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
    "src",
)

THE_WRITER = "database/projection.py"

_WRITE = re.compile(
    r"\b(INSERT INTO|UPDATE|DELETE FROM)\s+"
    r"(people|memberships|membership_roles|posts|organizations)\b([^\n]*)"
)

# (file, statement prefix): how many times it appears. Step numbers are the projector plan's.
ALLOWED: dict[tuple[str, str], int] = {
    # Deleting a person became withdrawing the records that name them (step 9c, 2026-09-23),
    # so nothing deletes a `people` row any more. The row outlives the person the fold stops
    # deriving, until step 8 makes delete-and-insert the only path for people too.
    # Mints the persistent post row. Stays: a post's id is stable and the row persists (R1, R4).
    ("database/posts.py", "INSERT INTO posts"): 1,
    # Derived columns enter the fold at step 10.
    ("database/posts.py", "UPDATE posts SET meta_headcount"): 1,
    # A post's organization and existence become claims at step 11.
    ("database/posts.py", "DELETE FROM posts"): 1,
    # Organizations become claims at step 11.
    ("database/organizations.py", "INSERT INTO organizations"): 3,
    ("database/organizations.py", "UPDATE organizations SET name"): 1,
    ("database/organizations.py", "UPDATE organizations SET meta_is_default"): 2,
    ("database/organizations.py", "DELETE FROM organizations"): 1,
    # Dev-only seed that truncates and reloads an export. Becomes "insert the facts, rebuild"
    # at step 8.
    ("scripts/seed_open_data_subset.py", "INSERT INTO organizations"): 1,
    ("scripts/seed_open_data_subset.py", "INSERT INTO posts"): 1,
    ("scripts/seed_open_data_subset.py", "INSERT INTO people"): 1,
    ("scripts/seed_open_data_subset.py", "INSERT INTO memberships"): 1,
    ("scripts/seed_open_data_subset.py", "DELETE FROM organizations"): 1,
}


def _source_files() -> list[str]:
    found = []
    for directory, _, filenames in os.walk(_SRC):
        if "frontend" in directory.split(os.sep):
            continue
        for filename in filenames:
            if filename.endswith(".py"):
                found.append(os.path.join(directory, filename))
    return sorted(found)


def _statements(path: str) -> list[str]:
    """Each write in the file as "VERB table rest-of-line", whitespace collapsed."""
    with open(path) as handle:
        text = handle.read()
    return [
        " ".join(f"{verb} {table}{rest}".split())
        for verb, table, rest in _WRITE.findall(text)
    ]


def _longest_allowed_prefix(relative: str, statement: str) -> str | None:
    matches = [
        prefix
        for (file, prefix) in ALLOWED
        if file == relative and statement.startswith(prefix)
    ]
    return max(matches, key=len) if matches else None


@pytest.mark.unit
def test_only_the_writer_writes_the_projection():
    found: dict[tuple[str, str], int] = {}
    unexpected: list[str] = []
    for path in _source_files():
        relative = os.path.relpath(path, _SRC)
        if relative == THE_WRITER:
            continue
        for statement in _statements(path):
            prefix = _longest_allowed_prefix(relative, statement)
            if prefix is None:
                unexpected.append(f"{relative}: {statement}")
            else:
                found[(relative, prefix)] = found.get((relative, prefix), 0) + 1

    assert not unexpected, (
        "a projection table is written outside database/projection.py:\n  "
        + "\n  ".join(unexpected)
        + "\nMove the write into the writer, or if a later step deletes it, allow-list it "
        "here with that step."
    )
    assert found == ALLOWED, (
        "the allow-list no longer matches the code. Entries whose count changed:\n  "
        + "\n  ".join(
            f"{file}: {prefix!r} expected {ALLOWED.get((file, prefix), 0)}, found {count}"
            for file, prefix in sorted(set(found) | set(ALLOWED))
            if (count := found.get((file, prefix), 0)) != ALLOWED.get((file, prefix), 0)
        )
    )


@pytest.mark.unit
def test_the_writer_writes_only_projection_tables():
    """The writer is for the projection. A fact table written here would be the one place the
    REVOKE at step 5 could not reach."""
    with open(os.path.join(_SRC, THE_WRITER)) as handle:
        text = handle.read()
    fact_write = re.compile(
        r"\b(INSERT INTO|UPDATE|DELETE FROM)\s+(source_records|claims|source_pages|changesets)\b"
    )
    assert not fact_write.findall(text), "database/projection.py must not write a fact table"
