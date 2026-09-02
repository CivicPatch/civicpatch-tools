"""Integration tests for `?as_of` on the memberships read — who held a post at a date.

The window is the membership's own interval: open at `first_seen_at`, closed at `closed_at`.
It lives here and not on the posts read, which is undated — a post is stable, so every one of
them belongs in the answer whatever date is asked about.

Real Postgres, because the date arithmetic (`::date + 1`, meaning the *end* of that day) and
the half-open interval are the things under test.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio

from database import divisions, memberships, organizations, people, posts
from database.database import get_pool

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_asof/government"
_BASE = "ocd-division/country:us/state:zz/place:zz_asof"

_LABEL = "Mayor"
_TOOK_OFFICE = datetime(2026, 3, 1, tzinfo=timezone.utc)
_HANDOVER = datetime(2026, 5, 1, tzinfo=timezone.utc)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        for table in ("posts", "divisions", "organizations", "people"):
            await cur.execute(
                f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_OCDID,)
            )
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed_succession() -> str:
    """One seat, two occupants: an outgoing mayor and the one who replaced them.

    Written straight to the table rather than through `record`, because the point is to
    control the observation window — `record` stamps it from the scrape.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        organization_id = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        post_id = await posts.find_or_create(cur, _OCDID, organization_id, "mayor", _BASE)

        for name, first_seen_at, closed_at in (
            ("Outgoing", _TOOK_OFFICE, _HANDOVER),
            ("Incoming", _HANDOVER, None),
        ):
            person_id = str(uuid.uuid4())
            await cur.execute(
                "INSERT INTO people (id, jurisdiction_ocdid, name) "
            "VALUES (%s, %s, %s)",
                (person_id, _OCDID, name),
            )
            await cur.execute(
                """
                INSERT INTO memberships
                    (post_id, organization_id, person_id,
                     first_seen_at, last_seen_at, closed_at, source_labels)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    post_id,
                    organization_id,
                    person_id,
                    first_seen_at,
                    closed_at or first_seen_at,
                    closed_at,
                    [_LABEL],
                ),
            )
        await conn.commit()
    return post_id


async def _rows_at(as_of: date | None) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await memberships.list_for_jurisdiction(cur, _OCDID, as_of)


async def _holders(as_of: date | None) -> int:
    """Occupancy is the number of memberships open at that moment — the posts read used to
    send a count of its own, windowed on sightings rather than on the interval."""
    return len(await _rows_at(as_of))


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_date_inside_a_closed_window_finds_the_person_who_left():
    """The whole point of keeping closed rows: "who held it then" outlives the tenure."""
    await _seed_succession()

    assert await _holders(date(2026, 4, 1)) == 1
    assert await _holders(date(2026, 6, 1)) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_seat_never_reads_as_double_occupied_at_the_handover():
    """Both rows touch 2026-05-01 — one closes, one opens. Counting the boundary twice would
    show two mayors on the day the office changed hands."""
    await _seed_succession()

    assert await _holders(date(2026, 5, 1)) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_today_matches_the_default():
    """The reason a date means end-of-day. At midnight semantics `as_of=today` would drop
    everything observed this morning and silently disagree with the unparameterised read."""
    await _seed_succession()

    assert await _holders(date.today()) == await _holders(None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_before_we_ever_looked_the_seat_is_empty_but_still_there_and_still_vouched_for():
    """Transaction time, so a date before our first scrape has no holders — but the post is
    not a temporal fact and neither is the vouching, and neither may vanish with the clock."""
    await _seed_succession()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await posts.list_for_jurisdiction(cur, _OCDID)

    assert len(rows) == 1
    assert await _holders(date(2026, 1, 1)) == 0
    assert rows[0]["_is_verified"] is True


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_membership_carries_the_interval_it_was_selected_on():
    """`as_of` filters on `first_seen_at`/`closed_at`, so a row has to show both — a reader
    drawing a tenure must not have to infer its end from a sighting."""
    await _seed_succession()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        rows = await memberships.list_for_jurisdiction(cur, _OCDID, date(2026, 4, 1))

    outgoing = next(row for row in rows if row["person_name"] == "Outgoing")
    assert outgoing["first_seen_at"] == _TOOK_OFFICE
    assert outgoing["closed_at"] == _HANDOVER

    open_now = await _rows_at(None)
    incoming = next(row for row in open_now if row["person_name"] == "Incoming")
    assert incoming["first_seen_at"] == _HANDOVER
    assert incoming["closed_at"] is None



@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_retired_person_still_reads_as_the_post_they_last_held():
    """`division_ocdid` falls back to the last closed membership, so leaving does not blank
    the card.

    The only field that still does: `PERSON_LABELS` and `PERSON_MEMBERSHIPS` are both
    `closed_at IS NULL`, so a retired person reads as no labels and no seats. `PERSON_DIVISION`
    — with `PERSON_START_DATE` and `PERSON_END_DATE`, which share its ordering — is what keeps
    them from vanishing entirely.

    Both people are asserted, because the fallback must not outrank an open membership: order
    it wrong and everyone reads as whatever they held longest ago.
    """
    await _seed_succession()

    roster = {
        person["name"]: person
        # `get_people`, not `get_roster`: the retired half of a succession holds no open
        # membership, so the roster read excludes them by definition now — and the claim here
        # is about the fallback, not about who is seated.
        for person in await people.get_people(jurisdiction_ocdid=_OCDID)
    }

    assert roster["Outgoing"]["division_ocdid"] == _BASE
    # Present tense: they hold nothing now, which is exactly why the fallback is needed.
    assert roster["Outgoing"]["memberships"] == []
    assert roster["Outgoing"]["labels"] == []

    assert roster["Incoming"]["division_ocdid"] == _BASE
    assert len(roster["Incoming"]["memberships"]) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_state_filter_carries_each_persons_jurisdiction():
    """`get_people(state=...)` used to SELECT `jurisdiction_ocdid` as its own column and merge
    it in. It now relies on `PERSON_JSON` already carrying it, so a caller grouping a whole
    state by jurisdiction still has something to group on."""
    await _seed_succession()

    by_state = await people.get_people(state="zz")
    seeded = [person for person in by_state if person["jurisdiction_ocdid"] == _OCDID]

    assert {person["name"] for person in seeded} == {"Outgoing", "Incoming"}

