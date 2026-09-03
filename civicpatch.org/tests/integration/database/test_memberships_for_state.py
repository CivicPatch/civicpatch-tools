"""Integration tests for `list_for_state` — a whole state's memberships, open and closed.

Real Postgres, because what is under test is the SQL: the state prefix scope, the inner join
onto `roles`, and the column aliases.

The alias test is the load-bearing one. `core.sheet.people_rows` reads rows by name, and
`dict.get` returns `None` for a key that is not there — so a rename on either side produces an
empty column in a live spreadsheet rather than an error anyone would notice.

Isolation: sentinel states 'zz' and 'zy', cleaned before and after each test.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from core.sheet.people_rows import HEADERS
from database import change_logs, divisions, memberships, organizations, posts
from database.database import get_pool

_ZZ = "ocd-jurisdiction/country:us/state:zz/place:zz_sheet/government"
_ZZ_DIVISION = "ocd-division/country:us/state:zz/place:zz_sheet"
_ZY = "ocd-jurisdiction/country:us/state:zy/place:zy_sheet/government"
_ZY_DIVISION = "ocd-division/country:us/state:zy/place:zy_sheet"
# The feed tests need a state no other test file seeds: the integration database is shared,
# and `zz` carries residue from several of them under different ocdids.
_ZX = "ocd-jurisdiction/country:us/state:zx/place:zx_feed/government"

_ROLE = "mayor"
_FIRST_TERM = datetime(2020, 1, 1, tzinfo=timezone.utc)
_STOOD_DOWN = datetime(2022, 1, 1, tzinfo=timezone.utc)
_SECOND_TERM = datetime(2024, 1, 1, tzinfo=timezone.utc)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid in (_ZZ, _ZY, _ZX):
            await cur.execute(
                "DELETE FROM memberships m USING posts p "
                "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
                (ocdid,),
            )
            for table in ("posts", "divisions", "organizations", "people"):
                await cur.execute(
                    f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (ocdid,)
                )
            await cur.execute(
                "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (ocdid,)
            )
            await cur.execute(
                "DELETE FROM change_logs WHERE jurisdiction_ocdid = %s", (ocdid,)
            )
        await cur.execute("DELETE FROM change_logs WHERE type = 'reorder_roles'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _add_membership(cur, ocdid, division, state, name, stints) -> str:
    """One person and their stints in one seat. Written straight to the table so the
    observation window is the test's to control, not a scrape's."""
    await cur.execute(
        "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
        "VALUES (%s, %s, 'local') ON CONFLICT DO NOTHING",
        (ocdid, state),
    )
    organization_id = await organizations.find_or_create(cur, ocdid)
    await divisions.find_or_create(cur, division, ocdid)
    post_id = await posts.find_or_create(cur, ocdid, organization_id, _ROLE, division)

    person_id = str(uuid.uuid4())
    await cur.execute(
        "INSERT INTO people (id, jurisdiction_ocdid, name, emails) "
        "VALUES (%s, %s, %s, %s)",
        (person_id, ocdid, name, ["mayor@zz.gov"]),
    )
    for first_seen_at, closed_at in stints:
        await cur.execute(
            """
            INSERT INTO memberships
                (post_id, organization_id, person_id,
                 first_seen_at, last_seen_at, closed_at, label, source_labels)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                post_id,
                organization_id,
                person_id,
                first_seen_at,
                closed_at or first_seen_at,
                closed_at,
                "Acting",
                ["Mayor", "Acting Mayor"],
            ),
        )
    return person_id


async def _seed_two_states():
    """A returning mayor in zz — one closed stint and a current one — and one in zy, which
    nothing scoped to zz may return."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await _add_membership(
            cur,
            _ZZ,
            _ZZ_DIVISION,
            "zz",
            "Ana Zed",
            [(_FIRST_TERM, _STOOD_DOWN), (_SECOND_TERM, None)],
        )
        await _add_membership(
            cur, _ZY, _ZY_DIVISION, "zy", "Bo Wye", [(_FIRST_TERM, None)]
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_every_sheet_header_is_a_column_the_query_returns():
    """The contract. `to_row` reads by name and `dict.get` swallows a miss, so a rename on
    either side shows up as a blank column in a live spreadsheet and nowhere else."""
    await _seed_two_states()

    rows = await memberships.list_for_state("zz")

    assert rows, "expected the sentinel state to return rows"
    assert set(HEADERS) <= set(rows[0])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_closed_membership_comes_back_too():
    """What separates this from `people.get_roster`, whose projection is `closed_at IS NULL`
    and so can never see a former officeholder."""
    await _seed_two_states()

    rows = await memberships.list_for_state("zz")

    closed = [row for row in rows if row["membership_closed_at"] is not None]
    open_now = [row for row in rows if row["membership_closed_at"] is None]
    assert len(closed) == 1
    assert len(open_now) == 1
    assert closed[0]["person_name"] == open_now[0]["person_name"] == "Ana Zed"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_another_state_is_not_returned():
    """The scope is a LIKE, so one that lost its anchor would quietly return the country."""
    await _seed_two_states()

    assert {row["person_name"] for row in await memberships.list_for_state("zz")} == {
        "Ana Zed"
    }
    assert {row["person_name"] for row in await memberships.list_for_state("zy")} == {
        "Bo Wye"
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_state_code_is_case_insensitive():
    await _seed_two_states()

    assert len(await memberships.list_for_state("ZZ")) == 2


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_seat_name_is_composed_and_role_label_does_not_leak():
    """`posts.label` was dropped by 148; the wording is built on read from the role and the
    division, and the raw `role_label` is not a column the sheet names."""
    await _seed_two_states()

    row = (await memberships.list_for_state("zz"))[0]

    assert row["post_label"] == "Mayor"
    assert "role_label" not in row


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_state_we_hold_nothing_for_is_empty_rather_than_an_error():
    """Maine and Delaware are exactly this today, and a header-only tab is a real case."""
    assert await memberships.list_for_state("zz") == []
    assert await memberships.count_for_state("zz") == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_count_matches_what_the_stream_yields():
    """`ensure_tab` sizes the grid from the count and `values.update` refuses a range past it,
    so a count that undershoots is a failed write on the largest states."""
    await _seed_two_states()

    assert await memberships.count_for_state("zz") == len(
        await memberships.list_for_state("zz")
    )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_stream_hands_back_chunks_rather_than_the_whole_state():
    """The point of the server-side cursor: memory is bounded by the chunk, not the state."""
    await _seed_two_states()

    chunks = [
        chunk async for chunk in memberships.stream_for_state("zz", chunk_size=1)
    ]

    assert [len(chunk) for chunk in chunks] == [1, 1]
    assert {row["membership_id"] for chunk in chunks for row in chunk} == {
        row["membership_id"] for row in await memberships.list_for_state("zz")
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_change_log_puts_its_state_on_the_sweep_feed():
    """The feed the whole sync runs on. Every mutation writes a change log on the cursor it
    mutates with, so this is what makes the sheet unforgettable — no endpoint calls out to it."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO change_logs (type, jurisdiction_ocdid) VALUES ('edit_person', %s)",
            (_ZX,),
        )
        await conn.commit()

    assert "zx" in await change_logs.states_changed_since(60)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_change_outside_the_window_is_not_swept():
    """The lookback is what replaces a stored cursor, and so a migration."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO change_logs (type, jurisdiction_ocdid, created_at) "
            "VALUES ('edit_person', %s, now() - interval '2 hours')",
            (_ZX,),
        )
        await conn.commit()

    assert "zx" not in await change_logs.states_changed_since(15)
    assert "zx" in await change_logs.states_changed_since(180)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_global_change_names_no_state():
    """A role rename changes labels everywhere and records no jurisdiction — it belongs to the
    nightly full sweep, not to any one state."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO change_logs (type, jurisdiction_ocdid) VALUES ('reorder_roles', NULL)"
        )
        await conn.commit()

    assert None not in await change_logs.states_changed_since(60)
