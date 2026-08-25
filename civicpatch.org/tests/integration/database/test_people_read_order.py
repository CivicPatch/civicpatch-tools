"""Every `ORDER BY` behind a person read has to end in a unique column.

Two of them pick a value rather than an order — `PERSON_OFFICE` takes `LIMIT 1`, and
`get_people_page` takes `LIMIT/OFFSET` — so a tie is not a cosmetic wobble: it decides which
office renders, or lets a page repeat somebody the next page then skips. The other two decide
the order of a document we commit to open-data, where an unstable order rewrites the file on
every publish.

Real Postgres, because the thing under test is what the planner hands back. Each test rewrites
the rows between two reads: an UPDATE moves a tuple to the end of the heap, so a sequential
scan returns a different order — which is exactly how this breaks in production, on the next
person somebody edits.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from database import divisions, organizations, people, posts
from database.database import get_pool

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

_OCDID = "ocd-jurisdiction/country:us/state:zz/place:zz_order/government"
_BASE = "ocd-division/country:us/state:zz/place:zz_order"
_SEEN_AT = datetime(2026, 3, 1, tzinfo=timezone.utc)

# One `updated_at` for everyone, which is what `get_people_page` sorts on. A real publish
# writes the whole roster in one transaction, so this is the normal case, not a contrived one.
_UPDATED_AT = datetime(2026, 3, 2, tzinfo=timezone.utc)

_COUNCIL = ["Ada Byron", "Bo Diddley", "Cy Twombly", "Di Prima", "Eve Babitz"]
_DUAL_ROLE = "Zed Twoseats"


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


async def _add_person(cur, name: str) -> str:
    person_id = str(uuid.uuid4())
    await cur.execute(
        "INSERT INTO people (id, jurisdiction_ocdid, name, updated_at) "
        "VALUES (%s, %s, %s, %s)",
        (person_id, _OCDID, name, _UPDATED_AT),
    )
    return person_id


async def _seat(cur, organization_id: str, person_id: str, role_id: str, label: str) -> str:
    post_id = await posts.find_or_create(
        cur, _OCDID, organization_id, role_id, _BASE, headcount=len(_COUNCIL)
    )
    await cur.execute(
        """
        INSERT INTO memberships
            (post_id, organization_id, person_id, first_seen_at, last_seen_at, source_labels)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (post_id, organization_id, person_id, _SEEN_AT, _SEEN_AT, [label]),
    )
    return post_id


async def _seed() -> dict[str, str]:
    """A council, plus one person sitting on two bodies at once. Returns that person's two
    post ids and what each one is called.

    Both of their memberships open on the same `first_seen_at`, which is what a single ingest
    produces — and `PERSON_OFFICE` orders on exactly that before taking one.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDID,),
        )
        await divisions.find_or_create(cur, _BASE, _OCDID)
        council = await organizations.find_or_create(cur, _OCDID, "Council")
        board = await organizations.find_or_create(cur, _OCDID, "Board")

        for name in _COUNCIL:
            person_id = await _add_person(cur, name)
            await _seat(cur, council, person_id, "council-member", "Council Member")

        # Same role and division on both seats, so `PERSON_MEMBERSHIPS` ties on the two columns
        # it sorts by before the id — two different bodies is what makes a second open
        # membership legal at all.
        both = await _add_person(cur, _DUAL_ROLE)
        seats = {
            await _seat(cur, council, both, "council-member", "Council Member"): "Council Member",
            await _seat(cur, board, both, "council-member", "Board Member"): "Board Member",
        }
        await conn.commit()
    return seats


async def _rewrite_rows():
    """Move some tuples to the end of the heap, which is what reorders an unordered scan.

    A *subset*, deliberately: updating every row moves them all together and preserves their
    relative order, so it proves nothing. Both tables are touched because the orderings under
    test live in both — the roster's own order is over `people`, and the office pick is over
    `memberships`.
    """
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE people SET updated_at = %s "
            "WHERE jurisdiction_ocdid = %s AND name < %s",
            (_UPDATED_AT, _OCDID, _COUNCIL[2]),
        )
        await cur.execute(
            """
            UPDATE memberships m SET last_seen_at = %s
            FROM organizations o
            WHERE m.organization_id = o.id AND o.jurisdiction_ocdid = %s
              AND o.name = 'Council'
            """,
            (_SEEN_AT, _OCDID),
        )
        await conn.commit()


async def _roster() -> list[dict]:
    return await people.get_people(jurisdiction_ocdid=_OCDID)


async def test_the_roster_is_the_same_document_after_the_rows_are_rewritten():
    """Covers three orderings at once, because all three are inside what this returns: the
    order of the people, the `office` each one gets, and the order of their `memberships`."""
    await _seed()

    before = await _roster()
    await _rewrite_rows()
    after = await _roster()

    assert [person["name"] for person in before] == sorted(_COUNCIL + [_DUAL_ROLE])
    assert before == after


async def test_the_office_of_a_dual_role_person_is_decided_by_the_tiebreak():
    """`PERSON_OFFICE` takes `LIMIT 1` over two rows sharing a `first_seen_at`, so the tiebreak
    picks a *value*, not an order — which office renders at all.

    Asserted against the rule rather than by comparing two reads: perturbing a subquery means
    moving heap tuples, and whether that actually reorders depends on what ran before. The rule
    is that the lower post id wins, whichever order the two were written in.
    """
    seats = await _seed()
    lowest = min(seats)

    zed = next(p for p in await _roster() if p["name"] == _DUAL_ROLE)

    assert len(zed["memberships"]) == 2
    assert zed["office"]["name"] == seats[lowest]
    assert [m["post_id"] for m in zed["memberships"]] == sorted(seats)


async def test_paging_loses_nobody_when_a_person_is_edited_between_pages():
    """Everyone shares an `updated_at`, which is what the page sorts on, so every row is a tie.

    The edit has to land *between* two pages — paging straight through perturbs nothing and
    would pass with no tiebreak at all. A reviewer saving a person while another reads page 2
    is the ordinary case, and under a non-total order it makes page 3 repeat somebody page 1
    already showed while two people are never shown at all.
    """
    await _seed()
    total, first_page = await people.get_people_page(_OCDID, limit=2, offset=0)
    assert total == len(_COUNCIL) + 1

    await _rewrite_rows()

    seen = [person["id"] for person in first_page]
    offset = 2
    while len(seen) < total:
        _, page = await people.get_people_page(_OCDID, limit=2, offset=offset)
        if not page:
            break
        seen.extend(person["id"] for person in page)
        offset += 2

    assert sorted(seen) == sorted(set(seen))
    assert len(seen) == total
