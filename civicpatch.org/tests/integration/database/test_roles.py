"""Integration tests for the role taxonomy SQL layer (database.roles).

These run against the real test DB so the unique indexes, NULLS NOT DISTINCT
scope dedup, hard-delete semantics, and change_logs emission are actually
exercised — not mocked.

Run with:
  mise run tcp-integration

Isolation: there is no per-test rollback, so every test confines its writes to a
sentinel scope that cannot collide with seeded data, and clean_scope wipes that
scope before and after each test.
"""
import pytest
import pytest_asyncio

from database.database import get_pool
from database.roles import (
    delete_role,
    get_role_config_per_level,
    reorder_roles_at_scope,
    replace_roles_at_scope,
)
from shared.schemas import RoleConfig, Role

_SCOPE = "ocd-jurisdiction/country:us/state:zz/place:testville/government"


async def _wipe_scope():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM roles WHERE scope = %s", (_SCOPE,))
        await cur.execute("DELETE FROM change_logs WHERE jurisdiction_ocdid = %s", (_SCOPE,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_scope():
    await _wipe_scope()
    yield
    await _wipe_scope()


def _entry(role, aliases=None, is_unique=False):
    return Role.model_validate({
        "label": role,
        "is_unique": is_unique,
        "aliases": aliases or [],
    })


async def _locality_config(ocdid=_SCOPE):
    per_level = await get_role_config_per_level(ocdid)
    local = per_level.get("locality")
    assert local is not None, "expected a locality level for the sentinel scope"
    return local


async def _change_log_types():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT type, user_id FROM change_logs WHERE jurisdiction_ocdid = %s", (_SCOPE,))
        return await cur.fetchall()


async def _canonical_order(ocdid=_SCOPE):
    local = await _locality_config(ocdid)
    return [r.key for r in local.roles]


async def _reorder_logs():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT type, changes FROM change_logs WHERE jurisdiction_ocdid = %s AND type = 'reorder_roles'",
            (_SCOPE,),
        )
        return await cur.fetchall()


async def _wipe_change_logs():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM change_logs WHERE jurisdiction_ocdid = %s", (_SCOPE,))
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_roles_round_trip():
    await replace_roles_at_scope(
        _SCOPE,
        [_entry("Mayor", ["mayor"]), _entry("Council Member", ["councilmember"])],
        None,
    )
    local = await _locality_config()
    names = {r.key for r in local.roles}
    assert {"Mayor", "Council Member"} <= names
    mayor = next(r for r in local.roles if r.key == "Mayor")
    assert "mayor" in mayor.aliases


@pytest.mark.asyncio
@pytest.mark.integration
async def test_add_emits_one_event_with_aliases_in_payload():
    """A single add_role event carries the term + its aliases in one payload;
    no separate per-alias events. user_id NULL for system actions."""
    await replace_roles_at_scope(_SCOPE, [_entry("Mayor", ["mayor"])], None)
    rows = await _change_log_types()
    assert len(rows) == 1, "expected one event per term, not one per alias"
    assert rows[0][0] == "add_role"
    assert rows[0][1] is None  # user_id NULL for system


@pytest.mark.asyncio
@pytest.mark.integration
async def test_removed_role_is_deleted():
    await replace_roles_at_scope(_SCOPE, [_entry("Mayor"), _entry("Clerk")], None)
    await replace_roles_at_scope(_SCOPE, [_entry("Mayor")], None)

    local = await _locality_config()
    names = {r.key for r in local.roles}
    assert "Mayor" in names
    assert "Clerk" not in names
    assert "delete_role" in {r[0] for r in await _change_log_types()}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_alias_sync_adds_and_disables():
    await replace_roles_at_scope(_SCOPE, [_entry("Mayor", ["mayor", "hizzoner"])], None)
    await replace_roles_at_scope(_SCOPE, [_entry("Mayor", ["mayor", "the mayor"])], None)

    local = await _locality_config()
    mayor = next(r for r in local.roles if r.key == "Mayor")
    assert "mayor" in mayor.aliases
    assert "the mayor" in mayor.aliases
    assert "hizzoner" not in mayor.aliases


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_role_hard_deletes_and_emits_log():
    await replace_roles_at_scope(_SCOPE, [_entry("Mayor")], None)
    await _wipe_change_logs()

    await delete_role("Mayor", _SCOPE, None)

    local = await _locality_config()
    assert "Mayor" not in {r.key for r in local.roles}
    assert "delete_role" in {r[0] for r in await _change_log_types()}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_replace_handles_mixed_ops_in_one_call():
    """A single PUT can keep, remove, and add in one transaction."""
    await replace_roles_at_scope(
        _SCOPE,
        [
            _entry("Mayor", aliases=["mayor"]),
            _entry("Clerk", aliases=["clerk"]),
        ],
        None,
    )
    await _wipe_change_logs()

    # In one PUT: keep Mayor; remove Clerk; add Sheriff
    await replace_roles_at_scope(
        _SCOPE,
        [
            _entry("Mayor", aliases=["mayor"]),
            _entry("Sheriff", aliases=["the sheriff"]),
        ],
        None,
    )

    local = await _locality_config()
    by_value = {r.key: r for r in local.roles}

    assert "Mayor" in by_value
    assert "Clerk" not in by_value
    assert "Sheriff" in by_value
    assert "the sheriff" in by_value["Sheriff"].aliases

    types = {r[0] for r in await _change_log_types()}
    assert "delete_role" in types          # Clerk removed
    assert "add_role" in types             # Sheriff added (alias delta in payload)


# ── reorder_roles_at_scope ──────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reorder_sets_priority_by_position():
    await replace_roles_at_scope(
        _SCOPE,
        [_entry("Council Member"), _entry("Mayor"), _entry("Clerk")],
        None,
    )

    await reorder_roles_at_scope(_SCOPE, ["Mayor", "Clerk", "Council Member"], None)

    assert await _canonical_order() == ["Mayor", "Clerk", "Council Member"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reorder_emits_one_event_with_before_after():
    await replace_roles_at_scope(_SCOPE, [_entry("Mayor"), _entry("Clerk")], None)
    await _wipe_change_logs()

    await reorder_roles_at_scope(_SCOPE, ["Clerk", "Mayor"], None)

    rows = await _reorder_logs()
    assert len(rows) == 1
    _, changes = rows[0]
    assert changes["after"] == ["Clerk", "Mayor"]
    assert set(changes["before"]) == {"Mayor", "Clerk"}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reorder_unchanged_order_is_noop():
    await replace_roles_at_scope(_SCOPE, [_entry("Mayor"), _entry("Clerk")], None)
    current = await _canonical_order()
    await _wipe_change_logs()

    await reorder_roles_at_scope(_SCOPE, current, None)

    assert await _reorder_logs() == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reorder_set_mismatch_raises():
    await replace_roles_at_scope(_SCOPE, [_entry("Mayor"), _entry("Clerk")], None)

    with pytest.raises(RuntimeError):
        await reorder_roles_at_scope(_SCOPE, ["Mayor", "Sheriff"], None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reorder_records_moved_roles_in_payload():
    await replace_roles_at_scope(_SCOPE, [_entry("Mayor"), _entry("Clerk")], None)
    await _wipe_change_logs()

    await reorder_roles_at_scope(_SCOPE, ["Clerk", "Mayor"], None, ["Clerk"])

    rows = await _reorder_logs()
    assert len(rows) == 1
    _, changes = rows[0]
    assert changes["moved"] == ["Clerk"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reorder_drops_unknown_moved_roles():
    await replace_roles_at_scope(_SCOPE, [_entry("Mayor"), _entry("Clerk")], None)
    await _wipe_change_logs()

    # "Sheriff" isn't part of the reorder — it must not leak into the audit payload.
    await reorder_roles_at_scope(_SCOPE, ["Clerk", "Mayor"], None, ["Clerk", "Sheriff"])

    _, changes = (await _reorder_logs())[0]
    assert changes["moved"] == ["Clerk"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_added_canonical_role_lands_at_bottom_priority():
    await replace_roles_at_scope(_SCOPE, [_entry("Mayor"), _entry("Clerk")], None)

    # Adding a role must not default to priority 0 (which would tie/jump the top).
    await replace_roles_at_scope(_SCOPE, [_entry("Mayor"), _entry("Clerk"), _entry("Sheriff")], None)

    assert (await _canonical_order())[-1] == "Sheriff"
