"""Integration tests for seating a person (database.memberships.assign).

Real Postgres: what `assign` does now is file a claim and rebuild the jurisdiction from the
facts, so the row it reports is one the fold derived, not one it wrote.

The tests below read that through `assign`'s result and the rows that come out, never through
the claim's own columns: the claim's shape is step 7's business and changes again with §20.1.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from core.post_derivation import DerivedMembership
from database import divisions, memberships, organizations, posts, projection
from database.database import get_pool
from tests.integration import factories

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_assign/government"
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


@pytest.mark.asyncio
@pytest.mark.integration
async def test_assigning_somebody_the_page_puts_nowhere_reports_no_move():
    """This test verified that seating an unseated person reported no move and wrote the
    label. It now seeds a person another organization's page listed, because every record puts
    its person in a post — an unparsed title in one too — so holding nothing here means having
    been read somewhere else."""
    person_id, post_id, _ = await _seed(
        label="Clerk", read_in="Office of the City Clerk"
    )

    result = await memberships.assign(person_id, post_id, "Mayor of Testville")

    assert result.change.field == "post_id"
    assert result.change.before is None
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT label FROM memberships WHERE id::text = %s", (result.membership_id,)
        )
        assert (await cur.fetchone())[0] == "Mayor of Testville"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_moving_reports_where_from_and_leaves_one_membership():
    """The `post_id` change's `before` is what lets the UI say "moved from X" rather than
    "assigned".

    This test verified that the old seat was closed and both rows survived. It now verifies
    that the person holds the new post alone, because the writer replaces a jurisdiction's
    open memberships with what the facts derive rather than closing what they drop; the
    interval the closed row used to carry is `membership_terms`, at step 15."""
    person_id, first, second = await _seed()

    result = await memberships.assign(person_id, second, None)

    assert result.change.before == first
    assert result.change.after == second
    assert await _open_posts(person_id) == [second]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_reassigning_to_the_same_seat_only_sets_the_label():
    """Naming a membership must not cost what the parser found in the page's own label.

    This test verified that against `upsert`, which would have overwritten `designations` with
    an empty array. It now verifies it against the rebuild, which re-derives them from the
    record every time: the label is the human's claim, the designations are the page's."""
    person_id, post_id, _ = await _seed(label="Mayor Position 8")

    result = await memberships.assign(person_id, post_id, "Renamed")

    # Same seat, so the change is the label rather than the post.
    assert (result.change.field, result.change.after) == ("label", "Renamed")
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT label, designations FROM memberships WHERE id::text = %s",
            (result.membership_id,),
        )
        assert await cur.fetchone() == ("Renamed", ["Position 8"])


async def _activity_count() -> int:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT count(*) FROM activity WHERE jurisdiction_ocdid = %s", (_OCDID,)
        )
        return (await cur.fetchone())[0]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_same_seat_under_the_same_label_is_refused():
    """A re-assign that changes nothing still recorded an "assigned" in the activity feed —
    a change nobody made, against a membership that did not move."""
    person_id, post_id, _ = await _seed()
    await memberships.assign(person_id, post_id, "Mayor of Testville")
    logged = await _activity_count()

    with pytest.raises(memberships.NothingToAssign):
        await memberships.assign(person_id, post_id, "Mayor of Testville")

    assert await _activity_count() == logged


@pytest.mark.asyncio
@pytest.mark.integration
async def test_clearing_the_label_on_the_same_seat_is_a_real_change():
    """`None` is not "no edit": it hands the field back to the scraper."""
    person_id, post_id, _ = await _seed()
    await memberships.assign(person_id, post_id, "Mayor of Testville")

    result = await memberships.assign(person_id, post_id, None)

    assert (result.change.field, result.change.after) == ("label", None)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unknown_post_raises_rather_than_seating_nobody():
    person_id, _, _ = await _seed()

    with pytest.raises(memberships.UnknownPost):
        await memberships.assign(
            person_id, "00000000-0000-0000-0000-000000000000", None
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_pick_made_mid_review_files_under_that_review():
    """Without an explicit `changeset_id`, an assignment always files under the live roster's
    changeset — wrong for a pick made from inside an in-progress review, which should show up
    as part of that review rather than as an unrelated jurisdiction edit."""
    person_id, post_id, _ = await _seed()
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
        await memberships.assign(
            person_id, post_id, "Mayor of Testville", changeset_id=review_changeset_id
        )

        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM activity WHERE changeset_id = %s AND type = 'assign_membership'",
                (review_changeset_id,),
            )
            assert await cur.fetchone() is not None
    finally:
        # `_wipe()` doesn't know about `changesets`/`activity` — clean up ourselves, or the
        # next test's teardown fails deleting the `organizations` row this still references.
        async with pool.connection() as conn, conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM activity WHERE changeset_id = %s", (review_changeset_id,)
            )
            await cur.execute(
                "DELETE FROM changesets WHERE id::text = %s", (review_changeset_id,)
            )
            await conn.commit()
