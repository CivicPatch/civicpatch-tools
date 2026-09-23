"""Integration tests for seating a person, through `POST /jurisdictions/{ocdid}/roster-edits`.

Real Postgres: an edit files claims and rebuilds the jurisdiction from the facts, so every row
read below is one the fold derived, not one the edit wrote.

Ported 2026-09-23 from `memberships.assign`, deleted with `PUT /memberships`. The tests read
the rows that come out, never the claim's own columns.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from core.post_derivation import DerivedMembership
from database import divisions, organizations, posts, projection
from database.database import get_pool
from database.users import SYSTEM_USER_ID
from schemas.jurisdictions import OfficeEdit, PersonEdit
from services.jurisdiction_edits import UnknownPost, edit_in_review, edit_published_roster
from shared.utils.membership_ids import membership_id
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_assign/government"
# These tests are about what seating does, not who did it; `assign` defaulted the same way.
_USER_ID = SYSTEM_USER_ID
_BASE = "ocd-division/country:us/state:zz/place:zz_assign"
_WARD_3 = f"{_BASE}/ward:3"
_PAGE = "https://zz.gov/council"
_SCRAPED_AT = datetime(2026, 3, 1, tzinfo=timezone.utc)


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_OCDID,),
        )
        # Claims and changesets before the organizations their records name (205, ON DELETE
        # RESTRICT); the records go with the changeset.
        await cur.execute(
            "DELETE FROM assertions WHERE changeset_id IN "
            "(SELECT id FROM changesets WHERE jurisdiction_ocdid = %s)",
            (_OCDID,),
        )
        for table in ("posts", "divisions", "changesets", "organizations", "people"):
            await cur.execute(
                f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_OCDID,)
            )
        await cur.execute("DELETE FROM jurisdictions WHERE jurisdiction_ocdid = %s", (_OCDID,))
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed(label: str = "Mayor", read_in: str | None = None) -> tuple[str, str, str]:
    """A person the page puts in the first post, and a second post to move them to.

    The record matters: a `people` row with nothing behind it does not exist to the fold, so a
    rebuild would derive the person away. Migration 217's backfill settled that for production.

    `read_in` names the organization whose page listed them, defaulting to the one both posts
    are in. Another organization is how somebody comes to hold nothing here.
    """
    person_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) "
            "VALUES (%s, %s, %s)",
            (person_id, _OCDID, "Assign Test"),
        )
        org = await organizations.find_or_create(cur, _OCDID)
        await divisions.find_or_create(cur, _BASE, _OCDID)
        await divisions.find_or_create(cur, _WARD_3, _OCDID)
        first = await posts.find_or_create(cur, _OCDID, org, "mayor", _BASE)
        second = await posts.find_or_create(cur, _OCDID, org, "council-member", _WARD_3)
        listed_by = (
            await organizations.find_or_create(cur, _OCDID, read_in) if read_in else org
        )
        await conn.commit()
    await factories.published_scrape(
        _OCDID,
        _SCRAPED_AT,
        {
            person_id: [
                {
                    "name": "Assign Test",
                    "label": label,
                    "source_url": _PAGE,
                    "organization_id": listed_by,
                }
            ]
        },
    )
    # What publishing the scrape would have done: the memberships a reader sees are the ones
    # the facts derive, and `assign` reads them to tell a move from a seating.
    async with pool.connection() as conn, conn.cursor() as cur:
        await projection.rebuild_from_facts(cur, _OCDID)
        await conn.commit()
    return person_id, first, second


async def _open_posts(person_id: str) -> list[str]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT post_id::text FROM memberships "
            "WHERE person_id::text = %s AND closed_at IS NULL",
            (person_id,),
        )
        return [row[0] for row in await cur.fetchall()]


async def _seat(person_id, post_id, label, changeset_id=None):
    """Put somebody in an office, the way the app does now.

    These tests called `memberships.assign`, deleted 2026-09-23 with `PUT /memberships`. The
    act is the same: a human says this person holds this post, under this name.
    """
    office = [OfficeEdit(id=post_id, membership_label=label)]
    edit = [PersonEdit(id=person_id, offices=office)]
    if changeset_id:
        return await edit_in_review(_OCDID, edit, _USER_ID, changeset_id)
    return await edit_published_roster(_OCDID, edit, _USER_ID)


async def _membership(person_id, post_id):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT label, designations FROM memberships WHERE id::text = %s",
            (membership_id(person_id, post_id),),
        )
        return await cur.fetchone()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_seating_somebody_the_page_puts_nowhere_gives_them_the_office():
    """This test verified that seating reported no move and wrote the label. It now verifies
    only that they hold the office under that name, because a roster edit answers with the
    changeset it filed and the caller re-reads the roster: where a move came from was
    `assign`'s to report, and `assign` is gone."""
    person_id, post_id, _ = await _seed(label="Clerk", read_in="Office of the City Clerk")

    await _seat(person_id, post_id, "Mayor of Testville")

    assert await _open_posts(person_id) == [post_id]
    assert (await _membership(person_id, post_id))[0] == "Mayor of Testville"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_moving_leaves_one_membership():
    """This test verified that a move reported where it came from and left one membership. It
    now verifies the second half only: the fold keeps one membership per organization, so the
    new office replaces the old without anything closing it."""
    person_id, first, second = await _seed()

    await _seat(person_id, second, None)

    assert await _open_posts(person_id) == [second]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_naming_a_seat_keeps_what_the_page_said_about_it():
    """Naming a membership must not cost what the parser found in the page's own label: the
    label is the human's claim, the designations are the page's, and the rebuild re-derives
    the second from the record every time."""
    person_id, post_id, _ = await _seed(label="Mayor Position 8")

    await _seat(person_id, post_id, "Renamed")

    assert await _membership(person_id, post_id) == ("Renamed", ["Position 8"])


async def _activity_count() -> int:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM activity WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        return (await cur.fetchone())[0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_saying_again_what_already_stands_records_nothing():
    """This test verified that a re-assign raised `NothingToAssign`. It now verifies that it
    files and logs nothing, because a roster edit that changes nothing is not an error — the
    editor sends every person on the screen, so saying the same thing twice is the normal
    case, not a mistake."""
    person_id, post_id, _ = await _seed()
    await _seat(person_id, post_id, "Mayor of Testville")
    logged = await _activity_count()

    await _seat(person_id, post_id, "Mayor of Testville")

    assert await _activity_count() == logged
    assert (await _membership(person_id, post_id))[0] == "Mayor of Testville"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_clearing_the_name_of_a_seat_hands_it_back_to_the_page():
    """`None` is not "no edit": it withdraws the human's claim, and the fold answers with
    whatever the page's own label derives."""
    person_id, post_id, _ = await _seed()
    await _seat(person_id, post_id, "Mayor of Testville")

    await _seat(person_id, post_id, None)

    assert (await _membership(person_id, post_id))[0] != "Mayor of Testville"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unknown_post_is_refused_rather_than_seating_nobody():
    """The fold ignores a claim naming a post it cannot find, so without this the edit would
    file a claim and do nothing."""
    person_id, _, _ = await _seed()

    with pytest.raises(UnknownPost):
        await _seat(person_id, "00000000-0000-0000-0000-000000000000", None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_pick_made_mid_review_files_under_that_review():
    """A pick made from inside an in-progress review belongs to it, rather than showing up as
    an unrelated jurisdiction edit."""
    # A different office from the one the page already put them in, or the edit says nothing.
    person_id, _, second = await _seed()
    review_changeset_id = str(uuid.uuid4())
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO changesets (id, kind, jurisdiction_ocdid, updated_at) "
            "VALUES (%s, 'scrape', %s, now())",
            (review_changeset_id, _OCDID),
        )
        await conn.commit()

    try:
        await _seat(person_id, second, "Mayor of Testville", review_changeset_id)

        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM assertions WHERE changeset_id = %s AND field_path = 'posts'",
                (review_changeset_id,),
            )
            assert await cur.fetchone() is not None
    finally:
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM assertions WHERE changeset_id = %s", (review_changeset_id,)
            )
            await cur.execute(
                "DELETE FROM changesets WHERE id::text = %s", (review_changeset_id,)
            )
            await conn.commit()
