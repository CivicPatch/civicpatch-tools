"""Integration tests for the cross-jurisdiction unmatched-text triage list.

Real Postgres: the query is `unnest` + `GROUP BY` over a `text[]`, and the ordering is the
product decision under test.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from core.post_derivation import DerivedMembership
from database import divisions, memberships, organizations, posts
from database.database import get_pool

_TOWNS = ("zz_alfa", "zz_bravo", "zz_charlie")
_OCDIDS = [
    f"ocd-jurisdiction/country:us/state:zz/place:{town}/government" for town in _TOWNS
]
_SEEN_AT = datetime(2026, 8, 1, tzinfo=timezone.utc)

# In three towns once each vs. in one town three times: same occurrence count, different
# leverage. This is the pair the ordering has to tell apart.
_WIDESPREAD = "At-Large"
_LOCAL = "Ward 3 (interim)"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for ocdid in _OCDIDS:
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
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed_member(
    cur, ocdid: str, division: str, unmatched: list[str], source_labels: list[str] | None = None
) -> str:
    person_id = str(uuid.uuid4())
    await cur.execute(
        "INSERT INTO people (id, jurisdiction_ocdid, name) "
            "VALUES (%s, %s, %s)",
        (person_id, ocdid, "Triage Test"),
    )
    organization_id = await organizations.find_or_create(cur, ocdid)
    await divisions.find_or_create(cur, division, ocdid)
    post_id = await posts.find_or_create(
        cur, ocdid, organization_id, "council-member", division
    )
    return await memberships.upsert(
        cur,
        DerivedMembership(
            person_id=person_id,
            unmatched_text=unmatched,
            source_labels=source_labels or [],
        ),
        post_id,
        organization_id,
        _SEEN_AT,
    )


async def _seed_spread():
    """`_WIDESPREAD` in three towns, `_LOCAL` three times in one."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for index, ocdid in enumerate(_OCDIDS):
            await cur.execute(
                "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
                "VALUES (%s, 'zz', 'local')", (ocdid, ), )
            base = f"ocd-division/country:us/state:zz/place:{_TOWNS[index]}"
            await _seed_member(cur, ocdid, f"{base}/ward:1", [_WIDESPREAD])

        base = f"ocd-division/country:us/state:zz/place:{_TOWNS[0]}"
        for ward in (2, 3, 4):
            await _seed_member(cur, _OCDIDS[0], f"{base}/ward:{ward}", [_LOCAL])
        await conn.commit()


_WHOLE_PAGE = (100, 0)


async def _rows() -> list[dict]:
    _total, rows = await memberships.unmatched_text(*_WHOLE_PAGE)
    return [row for row in rows if row["text"] in (_WIDESPREAD, _LOCAL)]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_breadth_outranks_frequency():
    """Both terms occur three times. The one spanning three towns is worth one parser rule;
    the one confined to a single town is that town's phrasing. Sorting on raw frequency would
    make these a coin toss."""
    await _seed_spread()

    rows = await _rows()

    assert [row["text"] for row in rows] == [_WIDESPREAD, _LOCAL]
    assert rows[0]["occurrences"] == rows[1]["occurrences"] == 3
    assert rows[0]["jurisdictions"] == 3
    assert rows[1]["jurisdictions"] == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_examples_name_the_towns_to_go_look_at():
    """A count alone is not actionable — the curator has to open one and see the real label."""
    await _seed_spread()

    rows = await _rows()

    assert sorted(rows[0]["examples"]) == sorted(_OCDIDS)
    assert rows[1]["examples"] == [_OCDIDS[0]]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_spelling_variants_are_one_gap_not_three():
    """`unmatched_text` keeps the source's raw casing and punctuation on purpose. Three towns
    writing the same phrase three ways is still one taxonomy gap, and grouping on the exact
    string would show three rows each looking a third as urgent as the real one.

    Case only — punctuation is trimmed upstream by `_unmatched`, covered by
    `test_parse_label_trims_punctuation_from_the_edges_of_unmatched`."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        for index, ocdid in enumerate(_OCDIDS):
            await cur.execute(
                "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
                "VALUES (%s, 'zz', 'local')", (ocdid, ), )
            base = f"ocd-division/country:us/state:zz/place:{_TOWNS[index]}"
            spelling = ("Finance Liaison", "finance liaison", "FINANCE LIAISON")[index]
            await _seed_member(cur, ocdid, f"{base}/ward:1", [spelling])
        await conn.commit()

    _total, rows = await memberships.unmatched_text(*_WHOLE_PAGE)

    assert len(rows) == 1
    assert rows[0]["jurisdictions"] == 3
    assert rows[0]["occurrences"] == 3


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_vacated_seat_drops_off_the_list():
    """Triage is about what is broken now. A term on a closed membership is a problem that
    resolved itself, and leaving it in inflates the queue with work nobody needs to do."""
    await _seed_spread()

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE memberships m SET closed_at = %s FROM posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = ANY(%s)", (_SEEN_AT, _OCDIDS[1:])
        )
        await conn.commit()

    rows = await _rows()

    assert rows[0]["text"] == _LOCAL
    assert [row["jurisdictions"] for row in rows if row["text"] == _WIDESPREAD] == [1]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_example_label_is_what_the_term_came_out_of():
    """The context a curator judges "is this a role?" on — and the *one* label carrying the
    term, not every office the person holds. Storing `parsed.labels` as parts rather than the
    joined `office.name` is what makes that answerable.

    Written beside `unmatched_text` in one statement rather than joined back to
    `source_records`, which can disagree — source records land at ingest, memberships are
    written at publish, so a stacked unpublished scrape would show a label that no longer
    produces this term."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_OCDIDS[0],),
        )
        base = f"ocd-division/country:us/state:zz/place:{_TOWNS[0]}"
        await _seed_member(
            cur,
            _OCDIDS[0],
            f"{base}/ward:1",
            ["Finance Liaison"],
            source_labels=["Council Member Ward 1, Finance Liaison", "Planning Board Member"],
        )
        await conn.commit()

    _total, rows = await memberships.unmatched_text(*_WHOLE_PAGE)

    row = next(r for r in rows if r["text"] == "Finance Liaison")
    assert row["example_label"] == "Council Member Ward 1, Finance Liaison"
    # The label carrying the term, not the other one the person also holds.
    assert row["text"] in row["example_label"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_page_reports_the_whole_total():
    """`total` counts distinct terms, not rows on the page — otherwise "page 1 of 1" would be
    the answer at every offset and the control would never advance."""
    await _seed_spread()

    total, first = await memberships.unmatched_text(1, 0)
    _total, second = await memberships.unmatched_text(1, 1)

    assert len(first) == 1 and len(second) == 1
    assert total >= 2
    assert first[0]["text"] != second[0]["text"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_offset_past_the_end_still_knows_the_total():
    """The reason `total` is its own query rather than a window function: a window yields no
    row to read it from once the offset overruns, and the pager would collapse to zero pages."""
    await _seed_spread()

    total, rows = await memberships.unmatched_text(10, 10_000)

    assert rows == []
    assert total >= 2
