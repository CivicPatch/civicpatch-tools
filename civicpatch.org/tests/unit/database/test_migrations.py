"""Every migration from 141 on is idempotent, and wrapped in a transaction.

Re-running one has to be a no-op rather than an error: a deploy that half-applies, a replay
against a database already at that version, and `migrate_down` followed by `migrate_up` all
depend on it.

The 140 files before the floor predate the rule and are deliberately not held to it — a
migration that has run somewhere is history, and `AGENTS.md` forbids editing one.
"""

import pathlib
import re

import pytest

pytestmark = pytest.mark.unit

MIGRATIONS = pathlib.Path(__file__).parents[3] / "database_operations" / "migrations"

# Everything numbered at or above this is held to the rule.
IDEMPOTENT_FROM = 141

# Each pattern is a DDL verb and the guard it must carry.
_GUARDS = (
    (r"\bDROP\s+(TABLE|INDEX|TYPE|VIEW)\b", "IF EXISTS"),
    (r"\bCREATE\s+(TABLE|INDEX|TYPE|VIEW)\b", "IF NOT EXISTS"),
    (r"\bDROP\s+COLUMN\b", "IF EXISTS"),
    (r"\bADD\s+COLUMN\b", "IF NOT EXISTS"),
)


def _held_to_the_rule() -> list[pathlib.Path]:
    return sorted(
        p
        for p in MIGRATIONS.glob("*.sql")
        if p.name[:3].isdigit() and int(p.name[:3]) >= IDEMPOTENT_FROM
    )


@pytest.mark.parametrize("path", _held_to_the_rule(), ids=lambda p: p.name)
def test_every_ddl_statement_is_guarded(path):
    sql = path.read_text()
    for verb, guard in _GUARDS:
        for match in re.finditer(verb, sql, re.IGNORECASE):
            tail = sql[match.end() : match.end() + 40]
            assert guard.lower() in tail.lower(), (
                f"{path.name}: `{match.group(0)}` needs `{guard}` — re-running this "
                f"migration would error instead of doing nothing"
            )


@pytest.mark.parametrize("path", _held_to_the_rule(), ids=lambda p: p.name)
def test_every_migration_is_one_transaction(path):
    sql = path.read_text().upper()
    assert "BEGIN;" in sql and "COMMIT;" in sql, (
        f"{path.name}: a migration that fails halfway must leave nothing behind"
    )


def test_every_up_has_a_down():
    """A migration with no way back cannot be rolled back on a bad deploy.

    Floored like the rest: 012 has never had one, and writing a rollback for a migration that
    ran two years ago is guesswork, not a fix.
    """
    held = {p.name for p in _held_to_the_rule()}
    ups = {n.removesuffix(".up.sql") for n in held if n.endswith(".up.sql")}
    downs = {n.removesuffix(".down.sql") for n in held if n.endswith(".down.sql")}
    assert ups - downs == set()
