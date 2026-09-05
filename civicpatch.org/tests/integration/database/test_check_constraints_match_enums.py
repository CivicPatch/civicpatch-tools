"""Every `CHECK (col = ANY (ARRAY[...]))` against the enum it copies.

Eleven constraints in this schema restate a Python enum in SQL. The enum is the readable
definition; the constraint is enforcement Postgres is uniquely able to do — it catches a stray
UPDATE from psql that no Python guard will ever see. What was missing is anything binding the
two, so a migration could drop a value from one and leave the other behind.

Migration 174 is the case in point: `PR_OPENED` left `PipelineIssueStatus` and the constraint
had to be remembered by hand. This is what remembers.

Real DB because the thing under test is the constraint definition; nothing in Python can
evaluate it.
"""

import re

import pytest

from database.changeset_batches import BatchKind, BatchStatus
from database.database import get_pool
from database.review_sessions import ReviewSessionEntryStatus
from schemas.assertions import AssertionKind, EntityType
from schemas.common import UserRole
from shared.schemas import RoleStatus
from shared.utils.statuses import ChangesetKind, DismissalReason, PipelineIssueStatus

# Constraint name → the enum it copies. `exact` says the constraint holds every member;
# a subset constraint names the members it is allowed to hold and no others.
EXACT = {
    "changesets_kind_check": ChangesetKind,
    "changesets_dismissed_reason_valid": DismissalReason,
    "pipeline_issues_status_check": PipelineIssueStatus,
    "assertions_kind_check": AssertionKind,
    "assertions_entity_type_check": EntityType,
    "changeset_batches_kind_check": BatchKind,
    "changeset_batches_status_check": BatchStatus,
    "roles_status_check": RoleStatus,
    "users_role_valid": UserRole,
    "review_session_entries_status_check": ReviewSessionEntryStatus,
}

# Deliberate subsets. An alias may only be proposed or accepted, never excluded — exclusion is
# a fact about a role, not about one of its spellings.
SUBSET = {
    "role_aliases_status_check": RoleStatus,
}

# No enum behind it: `active`/`inactive` exists only here and in the SQL that reads it.
# Listed so its absence is a recorded choice rather than an oversight.
NO_ENUM = {"jurisdictions_status_check"}

_QUOTED = re.compile(r"'([^']*)'::text")


async def _constraint_values() -> dict[str, set[str]]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            SELECT conname, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE contype = 'c' AND pg_get_constraintdef(oid) LIKE '%ANY (ARRAY%'
            """
        )
        return {name: set(_QUOTED.findall(definition)) for name, definition in await cur.fetchall()}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_each_constraint_holds_exactly_its_enum():
    found = await _constraint_values()
    mismatched = {
        name: (found.get(name), {member.value for member in enum})
        for name, enum in EXACT.items()
        if found.get(name) != {member.value for member in enum}
    }
    assert not mismatched, f"constraint and enum disagree: {mismatched}"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_subset_constraints_hold_nothing_their_enum_does_not():
    found = await _constraint_values()
    for name, enum in SUBSET.items():
        assert found.get(name), f"{name} not found"
        assert found[name] < {member.value for member in enum}, (
            f"{name} is declared a subset but holds {found[name]}"
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_every_vocabulary_constraint_is_accounted_for():
    """A new one must be mapped to its enum or explicitly recorded as having none — otherwise
    it is the twelfth hand-maintained copy and nothing is watching it."""
    found = await _constraint_values()
    assert set(found) == set(EXACT) | set(SUBSET) | NO_ENUM
