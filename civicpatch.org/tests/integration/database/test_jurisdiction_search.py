"""Integration test for search_jurisdictions_by_text against real Postgres.

Covers what unit tests cannot: the FTS match on search_text, the separately-counted
total, population ordering, and stable non-overlapping paging.

Run with: mise run tcp-integration
Isolation: sentinel state 'zs', cleaned before/after.
"""

import json

import pytest
import pytest_asyncio

from database.database import get_pool
from database.jurisdictions import (
    search_jurisdictions_by_text,
    search_jurisdictions_fuzzy,
)

_LEVELS = ["local", "counties"]

_COUNTY_OCDID = "ocd-jurisdiction/country:us/state:zs/county:sentinel/government"
_PLACE_A = "ocd-jurisdiction/country:us/state:zs/place:zstown/government"
_PLACE_B = "ocd-jurisdiction/country:us/state:zs/place:zsburg/government"


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("DELETE FROM jurisdictions WHERE state = 'zs'")
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _insert(ocdid, *, level, name, search_text, population, parents=None):
    # meta_parent_ocdids is a real column, resolved to names at read time — the boundary
    # overlay computes it, so fixtures must supply it rather than relying on the jsonb copy.
    data = {"name": name, "population": population}
    if parents is not None:
        data["parent_ocdids"] = parents
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO jurisdictions
                (jurisdiction_ocdid, state, level, data, updated_at, status,
                 search_text, meta_parent_ocdids)
            VALUES (%s, 'zs', %s, %s, now(), 'active', %s, %s)
            """,
            (ocdid, level, json.dumps(data), search_text, parents or []),
        )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_matches_on_search_text_not_on_name():
    # search_text carries the state code and name; the name column is never queried.
    await _insert(
        _PLACE_A,
        level="local",
        name="Zztown town",
        search_text="zstown town zs zsstate",
        population=100,
    )

    _total, by_state_name = await search_jurisdictions_by_text(
        "zstown:* & zsstate:*", _LEVELS, 10
    )

    assert [r.name for r in by_state_name] == ["Zztown town"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_every_token_must_match():
    await _insert(
        _PLACE_A,
        level="local",
        name="Zztown town",
        search_text="zstown town zs",
        population=100,
    )

    _total, matched = await search_jurisdictions_by_text("zstown:* & zs:*", _LEVELS, 10)
    _total, unmatched = await search_jurisdictions_by_text(
        "zstown:* & nosuchtoken:*", _LEVELS, 10
    )

    assert len(matched) == 1
    assert unmatched == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_results_are_ordered_by_population_descending():
    await _insert(
        _PLACE_A,
        level="local",
        name="Zzsmall town",
        search_text="zsshared zssmall zs",
        population=10,
    )
    await _insert(
        _PLACE_B,
        level="local",
        name="Zzbig city",
        search_text="zsshared zsbig zs",
        population=9000,
    )

    _total, results = await search_jurisdictions_by_text("zsshared:*", _LEVELS, 10)

    assert [r.name for r in results] == ["Zzbig city", "Zzsmall town"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_county_rows_are_searchable_and_carry_their_level():
    # The LOCAL/COUNTY badge reads `level`, so it has to survive the round trip.
    await _insert(
        _COUNTY_OCDID,
        level="counties",
        name="Sentinel County",
        search_text="sentinel county zs",
        population=500,
    )

    _total, results = await search_jurisdictions_by_text("sentinel:*", _LEVELS, 10)

    assert [(r.name, r.level) for r in results] == [("Sentinel County", "counties")]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_levels_outside_the_filter_are_excluded():
    # State rows exist to supply state names to search_text; they are never results.
    await _insert(
        "ocd-jurisdiction/country:us/state:zs/government",
        level="state",
        name="Zzstate",
        search_text="zsstate zs",
        population=1,
    )

    _total, results = await search_jurisdictions_by_text("zsstate:*", _LEVELS, 10)

    assert results == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_total_is_the_prelimit_count():
    # Drives "N of M" — a total equal to the limit would make the message a lie.
    for index in range(3):
        await _insert(
            f"ocd-jurisdiction/country:us/state:zs/place:zsmany{index}/government",
            level="local",
            name=f"Zzmany{index} city",
            search_text=f"zsmany zsmany{index} zs",
            population=index,
        )

    total, results = await search_jurisdictions_by_text("zsmany:*", _LEVELS, 1)

    assert total == 3
    assert len(results) == 1


@pytest.mark.asyncio
@pytest.mark.integration
async def test_total_is_correct_past_the_last_page():
    # count(*) OVER () would report 0 here, since a window count only rides back attached
    # to rows — so an out-of-range page would claim the search matched nothing.
    await _insert(
        _PLACE_A,
        level="local",
        name="Zztown town",
        search_text="zstown town zs",
        population=100,
    )

    total, results = await search_jurisdictions_by_text("zstown:*", _LEVELS, 10, 500)

    assert total == 1
    assert results == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_paging_is_stable_and_non_overlapping():
    for index in range(4):
        await _insert(
            f"ocd-jurisdiction/country:us/state:zs/place:zspage{index}/government",
            level="local",
            name=f"Zzpage{index} city",
            search_text=f"zspage zspage{index} zs",
            population=index,
        )

    seen = []
    for page in range(4):
        _total, rows = await search_jurisdictions_by_text("zspage:*", _LEVELS, 1, page)
        seen += [r.jurisdiction_ocdid for r in rows]

    assert len(seen) == 4
    assert len(set(seen)) == 4  # no row appears on two pages


@pytest.mark.asyncio
@pytest.mark.integration
async def test_parent_names_resolve_in_order_most_specific_first():
    # The ocdid holds only slugs; each display name lives on the parent's own row.
    await _insert(
        _COUNTY_OCDID,
        level="counties",
        name="Sentinel County",
        search_text="sentinel county zs",
        population=500,
    )
    await _insert(
        "ocd-jurisdiction/country:us/state:zs/government",
        level="state",
        name="Zzstate",
        search_text="zsstate zs",
        population=1,
    )
    await _insert(
        _PLACE_A,
        level="local",
        name="Zztown town",
        search_text="zstown town zs",
        population=100,
        parents=[_COUNTY_OCDID, "ocd-jurisdiction/country:us/state:zs/government"],
    )

    _total, results = await search_jurisdictions_by_text("zstown:*", _LEVELS, 10)

    assert [r.parent_names for r in results] == [["Sentinel County", "Zzstate"]]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_parent_names_is_empty_when_none_are_recorded():
    # All of NC and TN look like this — no parent_ocdids upstream at all.
    await _insert(
        _PLACE_B,
        level="local",
        name="Zzburg village",
        search_text="zsburg village zs",
        population=100,
    )

    _total, results = await search_jurisdictions_by_text("zsburg:*", _LEVELS, 10)

    assert [r.parent_names for r in results] == [[]]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_an_unresolvable_parent_is_skipped_not_fatal():
    # A parent listed but not synced (level ordering, or removed upstream) must not
    # drop the row itself from the results.
    await _insert(
        _PLACE_A,
        level="local",
        name="Zztown town",
        search_text="zstown town zs",
        population=100,
        parents=["ocd-jurisdiction/country:us/state:zs/county:ghost/government"],
    )

    _total, results = await search_jurisdictions_by_text("zstown:*", _LEVELS, 10)

    assert len(results) == 1
    assert results[0].parent_names == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fuzzy_matches_a_misspelled_token():
    await _insert(
        _PLACE_A,
        level="local",
        name="Zzattle city",
        search_text="zsattle city zs",
        population=100,
    )

    total, results = await search_jurisdictions_fuzzy(["zsatle"], _LEVELS, 10)

    assert total == 1
    assert [r.name for r in results] == ["Zzattle city"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fuzzy_requires_every_token_to_match():
    # ANDed, not ORed — otherwise a common token like "county" drags in everything.
    await _insert(
        _PLACE_A,
        level="local",
        name="Zzattle city",
        search_text="zsattle city zs",
        population=100,
    )

    _t, both = await search_jurisdictions_fuzzy(["zsatle", "city"], _LEVELS, 10)
    _t, one_bad = await search_jurisdictions_fuzzy(
        ["zsatle", "nowherenear"], _LEVELS, 10
    )

    assert len(both) == 1
    assert one_bad == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fuzzy_with_no_tokens_searches_nothing():
    # Guards the composed SQL: zero conditions would otherwise build "WHERE AND ...".
    assert await search_jurisdictions_fuzzy([], _LEVELS, 10) == (0, [])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_fuzzy_results_are_ordered_by_population():
    for name, pop in [("Zzattle city", 10), ("Zzattle town", 9000)]:
        await _insert(
            f"ocd-jurisdiction/country:us/state:zs/place:{name.split()[1]}{pop}/government",
            level="local",
            name=name,
            search_text=f"zsattle {name.split()[1]} zs",
            population=pop,
        )

    _total, results = await search_jurisdictions_fuzzy(["zsatle"], _LEVELS, 10)

    assert [r.population for r in results] == [9000, 10]
