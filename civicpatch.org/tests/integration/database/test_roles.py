"""Integration tests for the role taxonomy SQL layer (database.roles).

These run against the real test DB so the case-insensitive label index, the
slug-derived primary key, the upsert-not-replace semantics, and change_logs
emission are actually exercised — not mocked.

Run with:
  mise run tcp-integration

Isolation: there is no per-test rollback, and migration 109 leaves 29 seeded
roles in place, so the table cannot simply be wiped. Instead every test confines
its writes to sentinel labels under _SENTINEL_PREFIX, and clean_roles removes
those rows, wipes role change_logs, and restores the seeded rows' priorities
(which the reorder tests necessarily disturb) before and after each test.
"""
import pytest
import pytest_asyncio

from database.users import SYSTEM_USER_ID
from database.database import get_pool
from core.role_taxonomy import slugify_label
from database.roles import (
    deactivate_role,
    get_roles,
    reorder_roles,
    upsert_roles,
)
from schemas.roles import RoleInput
from shared.schemas import RoleStatus

_SENTINEL_PREFIX = "ZZ Test "
_SENTINEL_ID_PATTERN = "zz-test-%"
_ROLE_LOG_TYPES = ("add_role", "edit_role", "delete_role", "reorder_roles")


def _label(name: str) -> str:
    return f"{_SENTINEL_PREFIX}{name}"


async def _priority_snapshot():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT id, priority FROM roles")
        return await cur.fetchall()


async def _restore(snapshot):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        # role_aliases cascades on role delete, so the sentinel rows take their
        # aliases with them.
        await cur.execute("DELETE FROM roles WHERE id LIKE %s", (_SENTINEL_ID_PATTERN,))
        await cur.execute("DELETE FROM change_logs WHERE type = ANY(%s)", (list(_ROLE_LOG_TYPES),))
        for role_id, priority in snapshot:
            await cur.execute("UPDATE roles SET priority = %s WHERE id = %s", (priority, role_id))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_roles():
    snapshot = await _priority_snapshot()
    await _restore(snapshot)
    yield
    await _restore(snapshot)


def _entry(name, aliases=None, is_unique=False, status=RoleStatus.ACTIVE) -> RoleInput:
    return RoleInput(
        label=_label(name),
        status=status,
        is_unique=is_unique,
        aliases=aliases or [],
    )


async def _sentinel_roles():
    return [r for r in await get_roles() if r.label.startswith(_SENTINEL_PREFIX)]


async def _change_log_types():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT type, user_id FROM change_logs WHERE type = ANY(%s)", (list(_ROLE_LOG_TYPES),)
        )
        return await cur.fetchall()


async def _reorder_logs():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT type, changes FROM change_logs WHERE type = 'reorder_roles'")
        return await cur.fetchall()


async def _wipe_change_logs():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM change_logs WHERE type = ANY(%s)", (list(_ROLE_LOG_TYPES),))
        await conn.commit()


async def _current_order():
    return [r.label for r in await get_roles()]


async def _current_ids():
    """reorder_roles keys on id; the change_log it writes is in labels."""
    return [r.id for r in await get_roles()]


# ── upsert_roles ────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_roles_round_trip():
    await upsert_roles([_entry("Mayor", ["zz mayor"]), _entry("Council Member")], None)

    by_label = {r.label: r for r in await _sentinel_roles()}
    assert {_label("Mayor"), _label("Council Member")} <= set(by_label)
    assert "zz mayor" in by_label[_label("Mayor")].aliases


@pytest.mark.asyncio
@pytest.mark.integration
async def test_new_role_id_is_the_slug_of_its_label():
    """The PK is derived, not generated — and by the same expression migration
    109 used to backfill it."""
    await upsert_roles([_entry("Council Member")], None)

    role = next(r for r in await _sentinel_roles() if r.label == _label("Council Member"))
    assert role.id == slugify_label(_label("Council Member")) == "zz-test-council-member"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_emits_one_event_with_aliases_in_payload():
    """A single add_role event carries the term + its aliases in one payload;
    no separate per-alias events. A taxonomy change nobody signed is the system's, and since
    160 it is attributed to the system user rather than left null."""
    await upsert_roles([_entry("Mayor", ["zz mayor"])], None)

    rows = await _change_log_types()
    assert len(rows) == 1, "expected one event per term, not one per alias"
    assert rows[0][0] == "add_role"
    assert str(rows[0][1]) == SYSTEM_USER_ID


@pytest.mark.asyncio
@pytest.mark.integration
async def test_absent_role_is_left_alone():
    """Upsert, not replace: a label missing from a later call is untouched.
    Removal is deactivate_role and nothing else."""
    await upsert_roles([_entry("Mayor"), _entry("Clerk")], None)
    await upsert_roles([_entry("Mayor")], None)

    labels = {r.label for r in await _sentinel_roles()}
    assert _label("Mayor") in labels
    assert _label("Clerk") in labels
    assert "delete_role" not in {r[0] for r in await _change_log_types()}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_alias_sync_adds_and_disables():
    await upsert_roles([_entry("Mayor", ["zz mayor", "zz hizzoner"])], None)
    await upsert_roles([_entry("Mayor", ["zz mayor", "zz the mayor"])], None)

    mayor = next(r for r in await _sentinel_roles() if r.label == _label("Mayor"))
    assert "zz mayor" in mayor.aliases
    assert "zz the mayor" in mayor.aliases
    assert "zz hizzoner" not in mayor.aliases


@pytest.mark.asyncio
@pytest.mark.integration
async def test_alias_change_log_records_the_right_direction():
    """Pins the payload direction. `diff_aliases` once returned (removed, added)
    while its caller destructured added-first, so every event had the two lists
    swapped. Both are added-first now; this test is what would catch a re-flip."""
    await upsert_roles([_entry("Mayor", ["zz keep", "zz drop"])], None)
    await _wipe_change_logs()

    await upsert_roles([_entry("Mayor", ["zz keep", "zz new"])], None)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT changes FROM change_logs WHERE type = 'edit_role'")
        changes = (await cur.fetchone())[0]

    assert changes["aliases_added"] == ["zz new"]
    assert changes["aliases_removed"] == ["zz drop"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_candidate_alias_is_stored_but_not_returned():
    """Approval is the whole reason role_aliases is a table: an unapproved alias
    must survive in storage and stay invisible to the matcher."""
    await upsert_roles([_entry("Mayor", ["zz mayor"])], None)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO role_aliases (role_id, label, status) VALUES (%s, %s, 'candidate')",
            ("zz-test-mayor", "zz unapproved"),
        )
        await conn.commit()

    mayor = next(r for r in await _sentinel_roles() if r.label == _label("Mayor"))
    assert mayor.aliases == ["zz mayor"]

    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM role_aliases WHERE role_id = %s", ("zz-test-mayor",)
        )
        assert (await cur.fetchone())[0] == 2, "the candidate must still be stored"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_alias_is_unique_across_roles():
    """The array could not enforce this: one string aliasing two roles makes the
    matcher's answer arbitrary. Rejected before the write so the message can name
    both roles; role_aliases_label_lower_uq remains the concurrency backstop."""
    await upsert_roles([_entry("Mayor", ["zz shared"])], None)

    with pytest.raises(RuntimeError, match="claimed by both"):
        await upsert_roles([_entry("Clerk", ["zz shared"])], None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_alias_cannot_claim_another_roles_label():
    """The gap no index could close: role_aliases_label_lower_uq spans one table,
    so nothing stopped Clerk claiming 'Mayor'. get_role_alias_map lets the last
    role written win, so the winner depended on priority order."""
    await upsert_roles([_entry("Mayor")], None)

    with pytest.raises(RuntimeError, match="claimed by both"):
        await upsert_roles([_entry("Clerk", [_label("Mayor")])], None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_case_variant_aliases_in_one_payload_are_rejected():
    """diff_aliases treats the list as a set, so two case variants survive as two
    INSERTs and collide on lower(label)."""
    with pytest.raises(RuntimeError, match="more than once"):
        await upsert_roles([_entry("Mayor", ["zz dupe", "ZZ Dupe"])], None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_labels_reducing_to_one_slug_are_rejected():
    """unique (lower(label)) lets these through — they differ. The primary key
    does not, since both slug to the same id."""
    await upsert_roles([_entry("Council Member")], None)

    with pytest.raises(RuntimeError, match="reduce to the id"):
        await upsert_roles([_entry("Council/Member")], None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_conflicting_payload_writes_nothing():
    """The check is pre-flight, so a rejected PUT leaves no partial write behind
    — not the valid role ahead of the conflict, and no change_log."""
    await upsert_roles([_entry("Mayor")], None)
    await _wipe_change_logs()

    with pytest.raises(RuntimeError):
        await upsert_roles(
            [_entry("Clerk"), _entry("Sheriff", [_label("Mayor")])], None
        )

    assert {r.label for r in await _sentinel_roles()} == {_label("Mayor")}
    assert await _change_log_types() == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_upsert_handles_add_and_edit_in_one_call():
    """One PUT can leave a role untouched, edit another, and add a third."""
    await upsert_roles([_entry("Mayor", ["zz mayor"]), _entry("Clerk")], None)
    await _wipe_change_logs()

    await upsert_roles(
        [
            _entry("Mayor", ["zz mayor"]),                  # unchanged
            _entry("Clerk", is_unique=True),                # edited
            _entry("Sheriff", ["zz the sheriff"]),          # added
        ],
        None,
    )

    by_label = {r.label: r for r in await _sentinel_roles()}
    assert by_label[_label("Clerk")].is_unique is True
    assert "zz the sheriff" in by_label[_label("Sheriff")].aliases

    types = {r[0] for r in await _change_log_types()}
    assert types == {"edit_role", "add_role"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_added_role_sorts_last_on_unranked_priority():
    """A new role carries no priority, and `ORDER BY priority NULLS LAST` puts
    it at the bottom rather than tying for first."""
    await upsert_roles([_entry("Mayor"), _entry("Sheriff")], None)

    assert (await _current_order())[-2:] == [_label("Mayor"), _label("Sheriff")]


# ── deactivate_role ─────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deactivate_sets_inactive_and_emits_log():
    """Removal is soft: the row survives so seat history can, and the change_log
    still records the user's action as delete_role."""
    await upsert_roles([_entry("Mayor")], None)
    await _wipe_change_logs()

    assert await deactivate_role("zz-test-mayor", None) is True

    mayor = next(r for r in await _sentinel_roles() if r.label == _label("Mayor"))
    assert mayor.status == RoleStatus.INACTIVE
    assert "delete_role" in {r[0] for r in await _change_log_types()}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deactivate_unknown_role_is_false_and_logs_nothing():
    assert await deactivate_role("zz-test-nonexistent", None) is False
    assert await _change_log_types() == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_deactivate_twice_is_false():
    """Idempotent, and the second call must not emit a duplicate event."""
    await upsert_roles([_entry("Mayor")], None)
    await deactivate_role("zz-test-mayor", None)
    await _wipe_change_logs()

    assert await deactivate_role("zz-test-mayor", None) is False
    assert await _change_log_types() == []


# ── reorder_roles ───────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reorder_sets_priority_by_position():
    await upsert_roles([_entry("Mayor"), _entry("Clerk")], None)

    # Move the two sentinels to the front, keeping everything else in order.
    sentinels = ["zz-test-clerk", "zz-test-mayor"]
    rest = [role_id for role_id in await _current_ids() if role_id not in sentinels]
    await reorder_roles(sentinels + rest, None)

    assert (await _current_ids())[:2] == sentinels


@pytest.mark.asyncio
@pytest.mark.integration
async def test_upsert_without_priority_keeps_the_stored_order():
    """The config editor's save payload omits `priority`, so RoleInput defaults it
    to None. An omitted priority must not be written through as NULL — a single
    role edit would otherwise flatten every role's priority and destroy the
    ordering that reorder_roles just set."""
    await upsert_roles([_entry("Mayor"), _entry("Clerk")], None)
    sentinels = ["zz-test-clerk", "zz-test-mayor"]
    rest = [role_id for role_id in await _current_ids() if role_id not in sentinels]
    await reorder_roles(sentinels + rest, None)

    # Re-save in the shape the frontend sends: every role, no priority field.
    await upsert_roles([_entry("Mayor"), _entry("Clerk")], None)

    assert (await _current_ids())[:2] == sentinels


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reorder_emits_one_event_with_before_after():
    """Keyed on id, logged in labels: core.change_logs renders this payload
    straight into the activity feed, where a slug would not read."""
    await upsert_roles([_entry("Mayor")], None)
    before_ids = await _current_ids()
    before = await _current_order()
    await _wipe_change_logs()

    await reorder_roles([before_ids[-1], *before_ids[:-1]], None)
    after = [before[-1], *before[:-1]]

    rows = await _reorder_logs()
    assert len(rows) == 1
    _, changes = rows[0]
    assert changes["after"] == after
    assert changes["before"] == before


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reorder_unchanged_order_is_noop():
    await upsert_roles([_entry("Mayor")], None)
    current = await _current_ids()
    await _wipe_change_logs()

    await reorder_roles(current, None)

    assert await _reorder_logs() == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reorder_set_mismatch_raises():
    await upsert_roles([_entry("Mayor")], None)
    current = await _current_order()

    with pytest.raises(RuntimeError):
        await reorder_roles(current[:-1], None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reorder_records_moved_roles_in_payload():
    """moved_roles comes in as ids and is logged as labels, same as before/after."""
    await upsert_roles([_entry("Mayor")], None)
    before = await _current_ids()
    await _wipe_change_logs()

    await reorder_roles([before[-1], *before[:-1]], None, ["zz-test-mayor"])

    _, changes = (await _reorder_logs())[0]
    assert changes["moved"] == [_label("Mayor")]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reorder_drops_unknown_moved_roles():
    await upsert_roles([_entry("Mayor")], None)
    before = await _current_ids()
    await _wipe_change_logs()

    # "zz-test-sheriff" isn't part of the reorder — it must not leak into the
    # audit payload, and label_by_id has no entry for it to render.
    await reorder_roles(
        [before[-1], *before[:-1]], None, ["zz-test-mayor", "zz-test-sheriff"]
    )

    _, changes = (await _reorder_logs())[0]
    assert changes["moved"] == [_label("Mayor")]
