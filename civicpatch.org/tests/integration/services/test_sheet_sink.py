"""Integration tests for `sync_state` — the sequence of Sheets calls one state produces.

Real Postgres, fake Sheets. The database half has to be real because the row count drives the
grid size and the chunk offsets; the Google half is a recorder, because what is under test is
*which calls we would make*, and that is where the arithmetic lives.

The offsets are the risk. Chunked writes address themselves, so an off-by-one puts the second
chunk on top of the first — losing rows silently, with a successful-looking run.

Isolation: sentinel state 'zz', cleaned before and after each test.
"""

import re
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio

from core.sinks.sheet import (
    jurisdiction_rows,
    membership_rows,
    people_rows,
    post_rows,
)
from database import divisions, organizations, posts
from database.database import get_pool
from services.sinks import sheet as roster_sheet

_ZZ = "ocd-jurisdiction/country:us/state:zz/place:zz_sync/government"
_ZZ_DIVISION = "ocd-division/country:us/state:zz/place:zz_sync"
# A county that sorts *after* a municipality by ocdid — `zy` precedes `zz`, and within one
# state `county:` already precedes `place:`. Only a cross-state pair can tell level ordering
# apart from the query's ocdid ordering.
_ZZ_COUNTY = "ocd-jurisdiction/country:us/state:zz/county:zz_sync/government"
_ZY_LOCAL = "ocd-jurisdiction/country:us/state:zy/place:zy_sync/government"
_PEOPLE_TAB = "Live[People][ZZ]"
_MEMBERSHIPS_TAB = "Live[Memberships][ZZ]"
_POSTS_TAB = "Live[Posts][ZZ]"
_SEEN = datetime(2026, 1, 1, tzinfo=timezone.utc)
_SPAN = re.compile(r"!A(\d+):[A-Z]+(\d+)$")


class _Recorder:
    """A Sheets service that answers plausibly and remembers what it was asked to do.

    It models one thing beyond recording: **the grid persists**. Tabs it is asked to create stay
    created at their size, so a second sync sees the grid the first one left. The trim depends
    entirely on that — without it every sync looks like a fresh tab and the trim never fires.
    """

    def __init__(self):
        # Set to make the first data write raise, standing in for a Sheets outage mid-tab.
        self.explode_on_update = False
        self.updates: list[dict] = []
        self.clears: list[str] = []
        self.requests: list[dict] = []
        self.sheets: dict[str, dict] = {}

    # -- the googleapiclient shape: service.spreadsheets().values().update(...).execute()
    def spreadsheets(self):
        return self

    def values(self):
        return self

    def update(self, **kwargs):
        if self.explode_on_update and not kwargs["range"].endswith("!A1:J1"):
            raise RuntimeError("Sheets is down")
        self.updates.append(kwargs)
        return _Result({"updatedCells": len(kwargs["body"]["values"])})

    def clear(self, **kwargs):
        self.clears.append(kwargs["range"])
        return _Result({})

    def get(self, **kwargs):
        return _Result({"sheets": list(self.sheets.values())})

    def batchUpdate(self, **kwargs):
        replies = []
        for request in kwargs["body"]["requests"]:
            self.requests.append(request)
            if "addSheet" in request:
                properties = dict(request["addSheet"]["properties"])
                properties["sheetId"] = len(self.sheets) + 1
                self.sheets[properties["title"]] = {
                    "properties": properties,
                    "protectedRanges": [],
                }
                replies.append({"addSheet": {"properties": properties}})
            elif "updateSheetProperties" in request:
                wanted = request["updateSheetProperties"]["properties"]
                for sheet in self.sheets.values():
                    if sheet["properties"]["sheetId"] != wanted["sheetId"]:
                        continue
                    # Merged, not replaced: freezing the header is an updateSheetProperties
                    # carrying only `frozenRowCount`, and replacing would drop `rowCount`.
                    grid = dict(sheet["properties"].get("gridProperties", {}))
                    grid.update(wanted.get("gridProperties", {}))
                    sheet["properties"]["gridProperties"] = grid
        return _Result({"replies": replies})

    def spans(self, tab: str) -> list[tuple[int, int]]:
        """The first and last row of every write to one tab, in order. Filtered by tab because
        `sync_state` writes the people tab and the posts tab in one call."""
        found = [
            _SPAN.search(call["range"])
            for call in self.updates
            if f"'{tab}'!" in call["range"]
        ]
        return [
            (int(match.group(1)), int(match.group(2))) for match in found if match
        ]

    def rows_for(self, tab: str) -> list[list]:
        """Every data row written to one tab. The header is the write starting at row 1, which
        is what gets skipped — tabs have different widths, so the range's end is no guide."""
        rows = []
        for call in self.updates:
            if f"'{tab}'!" not in call["range"]:
                continue
            match = _SPAN.search(call["range"])
            if match and match.group(1) == "1":
                continue
            rows.extend(call["body"]["values"])
        return rows

    def clears_for(self, tab: str) -> list[str]:
        return [target for target in self.clears if f"'{tab}'!" in target]


class _Result:
    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


async def _wipe():
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING posts p "
            "WHERE m.post_id = p.id AND p.jurisdiction_ocdid = %s",
            (_ZZ,),
        )
        for table in ("posts", "divisions", "organizations", "people"):
            await cur.execute(
                f"DELETE FROM {table} WHERE jurisdiction_ocdid = %s", (_ZZ,)
            )
        await cur.execute(
            "DELETE FROM jurisdictions WHERE jurisdiction_ocdid = ANY(%s)",
            ([_ZZ, _ZZ_COUNTY, _ZY_LOCAL],),
        )
        # The gate outlives the data it fingerprints, so a leftover row would make the next
        # test's first sync look like a repeat and skip the writes it is asserting.
        #
        # Matched by suffix, not equality: a target is `{spreadsheet_id}/{tab}`, so the tab name
        # alone stopped matching when the spreadsheet became part of it — which showed up only
        # on the *second* run, the first having had nothing to leave behind.
        await cur.execute(
            "DELETE FROM output_hashes WHERE target LIKE ANY(%s)",
            (
                [
                    f"%/{tab}"
                    for tab in (
                        _PEOPLE_TAB,
                        _MEMBERSHIPS_TAB,
                        _POSTS_TAB,
                        roster_sheet.JURISDICTIONS_TAB,
                    )
                ],
            ),
        )
        await conn.commit()


@pytest_asyncio.fixture(autouse=True)
async def clean_sentinels():
    await _wipe()
    yield
    await _wipe()


async def _seed(count: int):
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_ZZ,),
        )
        organization_id = await organizations.find_or_create(cur, _ZZ)
        await divisions.find_or_create(cur, _ZZ_DIVISION, _ZZ)
        post_id = await posts.find_or_create(
            cur, _ZZ, organization_id, "mayor", _ZZ_DIVISION
        )
        for index in range(count):
            person_id = str(uuid.uuid4())
            await cur.execute(
                "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)",
                (person_id, _ZZ, f"Person {index:02d}"),
            )
            await cur.execute(
                """
                INSERT INTO memberships
                    (post_id, organization_id, person_id,
                     first_seen_at, last_seen_at, closed_at, source_labels)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                # All but the last are closed, so most rows are history — the thing git omits.
                (
                    post_id,
                    organization_id,
                    person_id,
                    _SEEN,
                    _SEEN,
                    None if index == count - 1 else _SEEN,
                    ["Mayor"],
                ),
            )
        await conn.commit()


async def _sync(
    state: str,
    chunk_size: int,
    recorder: _Recorder | None = None,
    spreadsheet_id: str = "test-sheet",
) -> _Recorder:
    recorder = recorder or _Recorder()
    with (
        patch("lib.sheets.get_service", return_value=recorder),
        patch("services.entry_sheet.spreadsheet_id", return_value=spreadsheet_id),
    ):
        await roster_sheet.sync_state(state, chunk_size=chunk_size)
    return recorder


@pytest.mark.asyncio
@pytest.mark.integration
async def test_chunks_are_written_contiguously_below_the_header():
    """Five rows at two a chunk: header, then 2+2+1, each starting where the last ended."""
    await _seed(5)

    recorder = await _sync("zz", chunk_size=2)

    assert recorder.spans(_PEOPLE_TAB) == [(1, 1), (2, 3), (4, 5), (6, 6)]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_header_is_written_first_and_is_the_full_width():
    await _seed(3)

    recorder = await _sync("zz", chunk_size=2)

    assert recorder.updates[0]["body"]["values"] == [people_rows.HEADERS]
    assert recorder.updates[0]["range"].endswith("!A1:J1")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_grid_is_sized_for_the_rows_before_anything_is_written():
    """`values.update` refuses a range past the grid, so this has to happen first or Texas
    fails on its first write while every small state passes."""
    await _seed(5)

    recorder = await _sync("zz", chunk_size=2)

    grid = recorder.requests[0]["addSheet"]["properties"]["gridProperties"]
    assert grid == {"rowCount": 6, "columnCount": len(people_rows.HEADERS)}


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_trim_starts_at_the_first_row_this_run_did_not_write():
    """A state that lost people must not keep the tail of the previous sync.

    Two syncs, because the grid never shrinks: the first sizes it to 6 rows, the second writes
    only 4, and rows 5-6 are last run's leftovers."""
    await _seed(5)
    # One recorder across both syncs, so the second sees the grid the first left at 6 rows.
    recorder = await _sync("zz", chunk_size=10)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "DELETE FROM memberships m USING people p WHERE m.person_id = p.id "
            "AND p.jurisdiction_ocdid = %s AND p.name IN (%s, %s)",
            (_ZZ, "Person 00", "Person 01"),
        )
        await cur.execute(
            "DELETE FROM people WHERE jurisdiction_ocdid = %s AND name IN (%s, %s)",
            (_ZZ, "Person 00", "Person 01"),
        )
        await conn.commit()

    recorder.updates.clear()
    recorder.clears.clear()
    await _sync("zz", chunk_size=10, recorder=recorder)

    assert recorder.spans(_PEOPLE_TAB) == [(1, 1), (2, 4)]
    assert recorder.clears_for(_PEOPLE_TAB) == [f"'{_PEOPLE_TAB}'!A5:J"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_state_with_nobody_writes_a_header_and_trims_the_rest():
    """Maine and Delaware today. `_MINIMUM_ROWS` keeps the grid at 2, so row 2 is addressable
    and last run's single row still gets cleared."""
    recorder = await _sync("zz", chunk_size=2)

    assert recorder.spans(_PEOPLE_TAB) == [(1, 1)]
    assert recorder.clears_for(_PEOPLE_TAB) == [f"'{_PEOPLE_TAB}'!A2:J"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_closed_memberships_reach_the_sheet():
    """Four of the five seeded rows are closed. Git would render one; the sheet renders all."""
    await _seed(5)

    recorder = await _sync("zz", chunk_size=10)

    closed = membership_rows.HEADERS.index("membership_closed_at")
    written = recorder.rows_for(_MEMBERSHIPS_TAB)
    assert len(written) == 5
    assert sum(1 for row in written if row[closed]) == 4


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_tab_is_named_for_its_state():
    await _seed(1)

    recorder = await _sync("zz", chunk_size=2)

    assert roster_sheet.people_tab("zz") == _PEOPLE_TAB
    assert roster_sheet.memberships_tab("zz") == _MEMBERSHIPS_TAB
    assert roster_sheet.posts_tab("zz") == _POSTS_TAB
    assert {_PEOPLE_TAB, _MEMBERSHIPS_TAB, _POSTS_TAB} == {
        call["range"].split("'")[1] for call in recorder.updates
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_posts_tab_is_written_alongside_the_people_tab():
    """A seat nobody holds cannot appear on the roster tab, which is one row per membership —
    so the posts tab is the only place a curator sees it before inventing a near-miss."""
    await _seed(2)

    recorder = await _sync("zz", chunk_size=10)

    [post] = recorder.rows_for(_POSTS_TAB)
    assert post[post_rows.HEADERS.index("post_label")] == "Mayor"
    assert post[post_rows.HEADERS.index("post_role_id")] == "mayor"
    assert "post_is_verified" not in post_rows.HEADERS


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_posts_tab_is_sized_and_trimmed_like_the_people_tab():
    await _seed(2)

    recorder = await _sync("zz", chunk_size=10)

    # No trim: the grid is sized to rows+header, so a full tab has nothing below it.
    assert recorder.spans(_POSTS_TAB) == [(1, 1), (2, 2)]
    assert recorder.clears_for(_POSTS_TAB) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_the_jurisdiction_tab_covers_every_state_in_one_flat_tab():
    """The dropdown source. Sheets validation points at one contiguous range, so this cannot be
    split per state — which is exactly what lets `Entry[Roster]` accept any state."""
    await _seed(1)

    recorder = _Recorder()
    with (
        patch("lib.sheets.get_service", return_value=recorder),
        patch("services.entry_sheet.spreadsheet_id", return_value="test-sheet"),
    ):
        written = await roster_sheet.sync_jurisdictions(chunk_size=500)

    tab = roster_sheet.JURISDICTIONS_TAB
    assert written >= 1
    assert recorder.updates[0]["body"]["values"] == [jurisdiction_rows.HEADERS]
    # Column A is the ocdid, because that is the range the dropdown points at.
    assert _ZZ in [row[0] for row in recorder.rows_for(tab)]
    # A fresh grid is sized to fit exactly, so there is nothing below to trim.
    assert recorder.clears_for(tab) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_every_county_is_listed_before_any_municipality():
    """A volunteer picks the county, then the places inside it, so counties lead the dropdown."""
    await _seed(1)
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'counties'), (%s, 'zy', 'local')",
            (_ZZ_COUNTY, _ZY_LOCAL),
        )
        await conn.commit()

    recorder = _Recorder()
    with (
        patch("lib.sheets.get_service", return_value=recorder),
        patch("services.entry_sheet.spreadsheet_id", return_value="test-sheet"),
    ):
        await roster_sheet.sync_jurisdictions(chunk_size=500)

    level = jurisdiction_rows.HEADERS.index("level")
    levels = [row[level] for row in recorder.rows_for(roster_sheet.JURISDICTIONS_TAB)]
    assert levels == sorted(levels, key=roster_sheet.ENTRY_LEVELS.index)
    # The pair that ocdid ordering alone would have put the other way round.
    ocdids = [row[0] for row in recorder.rows_for(roster_sheet.JURISDICTIONS_TAB)]
    assert ocdids.index(_ZZ_COUNTY) < ocdids.index(_ZY_LOCAL)


async def _seed_two_stints() -> None:
    """One person, one seat, twice: an earlier closed stint and a current one."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_ZZ,),
        )
        organization_id = await organizations.find_or_create(cur, _ZZ)
        await divisions.find_or_create(cur, _ZZ_DIVISION, _ZZ)
        post_id = await posts.find_or_create(
            cur, _ZZ, organization_id, "mayor", _ZZ_DIVISION
        )
        person_id = str(uuid.uuid4())
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)",
            (person_id, _ZZ, "Ana Zed"),
        )
        for closed_at in (_SEEN, None):
            await cur.execute(
                """
                INSERT INTO memberships
                    (post_id, organization_id, person_id,
                     first_seen_at, last_seen_at, closed_at, source_labels)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (post_id, organization_id, person_id, _SEEN, _SEEN, closed_at, ["Mayor"]),
            )
        await conn.commit()


@pytest.mark.asyncio
@pytest.mark.integration
async def test_no_trim_when_the_data_fills_the_grid_exactly():
    """`ensure_tab` sizes the grid to rows+header, so a full tab has nothing below it. Asking
    to clear the row after the last one is out of bounds, not a no-op — WA hit this at 1,617."""
    await _seed(3)

    recorder = await _sync("zz", chunk_size=10)

    assert recorder.spans(_PEOPLE_TAB) == [(1, 1), (2, 4)]
    assert recorder.clears_for(_PEOPLE_TAB) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_returning_official_is_one_person_and_two_memberships():
    """The whole reason the tabs are separate. Counting the people tab must give people —
    before the split this person appeared twice and a curator would read two officials."""
    await _seed_two_stints()

    recorder = await _sync("zz", chunk_size=10)

    people = recorder.rows_for(_PEOPLE_TAB)
    seats = recorder.rows_for(_MEMBERSHIPS_TAB)
    assert len(people) == 1
    assert len(seats) == 2
    assert {row[membership_rows.HEADERS.index("person_id")] for row in seats} == {
        people[0][people_rows.HEADERS.index("person_id")]
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_someone_who_never_held_a_seat_is_still_a_person():
    """The tab a curator scans for a near-miss name — exactly the person about to be re-added
    under a slightly different spelling."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "INSERT INTO jurisdictions (jurisdiction_ocdid, state, level) "
            "VALUES (%s, 'zz', 'local')",
            (_ZZ,),
        )
        await cur.execute(
            "INSERT INTO people (id, jurisdiction_ocdid, name) VALUES (%s, %s, %s)",
            (str(uuid.uuid4()), _ZZ, "Never Seated"),
        )
        await conn.commit()

    recorder = await _sync("zz", chunk_size=10)

    assert len(recorder.rows_for(_PEOPLE_TAB)) == 1
    assert recorder.rows_for(_MEMBERSHIPS_TAB) == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_second_sync_of_the_same_roster_writes_nothing():
    """The sweep runs every 5 minutes against a 15-minute lookback, so it selects the same
    change three times. Measured before this gate: one email edit to Seattle produced three
    open-data commits, two of them empty, and three full rewrites of Washington's tabs —
    about 9,700 rows re-uploaded for one changed cell."""
    await _seed(3)

    first = await _sync("zz", chunk_size=2)
    second = await _sync("zz", chunk_size=2)

    assert first.updates, "the first sync must actually write"
    assert second.updates == []
    assert second.clears == []


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_changed_roster_is_written_again():
    """The gate must not be a one-way door: the point is to skip repeats, not to stop syncing."""
    await _seed(3)
    await _sync("zz", chunk_size=2)

    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "UPDATE people SET name = 'Renamed Person' "
            "WHERE jurisdiction_ocdid = %s AND name = (SELECT min(name) FROM people "
            "WHERE jurisdiction_ocdid = %s)",
            (_ZZ, _ZZ),
        )
        await conn.commit()

    assert (await _sync("zz", chunk_size=2)).updates


@pytest.mark.asyncio
@pytest.mark.integration
async def test_a_failed_write_records_no_hash_so_the_retry_still_fires():
    """The one that loses data if it is wrong. Recording the hash before the write lands would
    mark the tab current when it is half-written, and every retry would then skip it — the tab
    stays wrong until its content changes again, which may be never."""
    await _seed(3)

    exploding = _Recorder()
    exploding.explode_on_update = True
    with pytest.raises(RuntimeError):
        await _sync("zz", chunk_size=2, recorder=exploding)

    # Nothing recorded, so an ordinary retry writes.
    assert (await _sync("zz", chunk_size=2)).updates


@pytest.mark.asyncio
@pytest.mark.integration
async def test_pointing_at_a_different_spreadsheet_writes_it():
    """Switching ENTRY_SPREADSHEET_ID must not be skipped as "already written".

    The hash is of the rows about to be written, rendered from the database — not of what the
    sheet holds. So the same rows hash the same whichever file they are going to, and keying the
    gate on the tab name alone made the second spreadsheet look already-current. It stays empty,
    and nothing says so.

    This is not a prod-vs-dev concern; it is one stack repointed, which happened on 2026-09-04.
    """
    await _seed(2)

    first = await _sync("zz", chunk_size=2)
    second = await _sync("zz", chunk_size=2, spreadsheet_id="a-different-spreadsheet")

    assert first.updates, "the first sheet must be written"
    assert second.updates, "so must a different sheet holding the same rows"
