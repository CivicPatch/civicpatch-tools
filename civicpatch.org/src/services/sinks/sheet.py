"""The roster, mirrored into the data-entry spreadsheet — one tab per state, with history.

The second sink alongside open-data, and unlike git it carries closed memberships.

Tabs are replaced whole rather than patched, which is what makes a retry safe. `_replace_rows`
owns the ordering: size the grid before writing (`values.update` refuses a range past it), trim
after the last chunk (clearing first would empty the tab if a later chunk failed).

Spec: `.scratch/2026-09-03-plan-*.md`.
"""

import asyncio
import hashlib
import logging
from typing import AsyncGenerator, Callable

from core.output_hash import row_line
from core.sinks.sheet import (
    jurisdiction_rows,
    membership_rows,
    people_rows,
    post_rows,
    widths_for,
)
from database import jurisdictions as jurisdictions_db
from database import output_hashes as output_hashes_db
from database import memberships
from database import people as people_db
from database import posts as posts_db
from lib import sheets
from services import entry_sheet

logger = logging.getLogger(__name__)

# Row 1 is the header.
_FIRST_DATA_ROW = 2

# What a volunteer may enter a roster for. A domain decision, so not in the query.
ENTRY_LEVELS = ["local", "counties"]

JURISDICTIONS_TAB = "Live[Jurisdictions]"


# Three tabs per state, one grain each: count the rows and you get people, memberships, seats.
def people_tab(state: str) -> str:
    """One tab per state. `Live[...]` groups the app-owned tabs together in the tab bar."""
    return f"Live[People][{state.upper()}]"


def memberships_tab(state: str) -> str:
    return f"Live[Memberships][{state.upper()}]"


def posts_tab(state: str) -> str:
    return f"Live[Posts][{state.upper()}]"


def ordered_tabs(states: list[str]) -> list[str]:
    """The whole tab bar: entry, jurisdictions, then each state's three tabs together.

    State first because that is how the sheet is worked — one state at a time, all three grains
    side by side. Entry leads because it is the tab a volunteer actually opens.
    """
    tabs = [entry_sheet.ROSTER_TAB, JURISDICTIONS_TAB]
    for state in sorted(states):
        tabs += [people_tab(state), memberships_tab(state), posts_tab(state)]
    return tabs


Chunks = Callable[[], AsyncGenerator[list[list[str]], None]]


def describe(written: int | None) -> str:
    """For logs. `None` is a tab left alone, which is not the same as a tab that legitimately
    holds nothing — Maine and Delaware have zero memberships."""
    return "unchanged" if written is None else f"{written} rows"


async def _content_hash(headers: list[str], chunks: Chunks) -> str:
    """Stream the rows once to fingerprint them, holding one line at a time.

    A factory rather than a generator because this consumes one and the write consumes another;
    a generator is single-use. The second pass costs one more query — 50 ms for Texas, the
    largest state — against three Sheets requests carrying 3.5 MB, so it pays for itself the
    moment a tab is unchanged.
    """
    digest = hashlib.sha256()
    digest.update(row_line(headers).encode())
    async for block in chunks():
        for row in block:
            digest.update(row_line(row).encode())
    return digest.hexdigest()


async def _replace_rows(
    tab: str,
    headers: list[str],
    total: int,
    chunks: Chunks,
) -> int | None:
    """Make a tab hold exactly the header plus these rows, and nothing else.

    Returns None when the tab already holds them — the sweep re-selects the same change three
    times over its lookback, so two of every three calls have nothing to do, and a state rewrite
    is ~9,700 rows.

    Threaded because `googleapiclient` is synchronous and would block the event loop.
    """
    # The spreadsheet is part of the destination, not just the tab. The hash is of the rows
    # about to be written, so the same rows hash the same whichever file they go to — keying on
    # the tab name alone made a *different* spreadsheet look already-written, and it stayed
    # empty with nothing to say so. Happened 2026-09-04 on a sheet swap.
    #
    # Deliberately not done for the parquet and open-data sinks. Same shape, but a bucket and a
    # git repo are provisioned once and do not move, where a spreadsheet gets copied and swapped
    # by hand. One real failure is not a reason to guard two imagined ones.
    spreadsheet_id = entry_sheet.spreadsheet_id()
    target = f"{spreadsheet_id}/{tab}"

    content_hash = await _content_hash(headers, chunks)
    if (await output_hashes_db.get_hashes([target])).get(target) == content_hash:
        logger.info(f"{tab}: unchanged, left alone")
        return None

    grid_rows = await asyncio.to_thread(
        sheets.ensure_tab, spreadsheet_id, tab, total + 1, widths_for(headers)
    )
    await asyncio.to_thread(sheets.write_rows, spreadsheet_id, tab, [headers], 1)

    row = _FIRST_DATA_ROW
    async for block in chunks():
        await asyncio.to_thread(sheets.write_rows, spreadsheet_id, tab, block, row)
        row += len(block)

    # Whatever the last run left below this one — but only if there is a row there to clear.
    # Data that exactly fills the grid leaves nothing below it, and a range past the end is an
    # error, not a no-op.
    if row <= grid_rows:
        await asyncio.to_thread(
            sheets.clear_rows_from, spreadsheet_id, tab, row, len(headers)
        )

    # Only after every chunk landed: recording earlier would leave a half-written tab marked
    # current, and the retry would skip it.
    await output_hashes_db.record_hashes({target: content_hash})
    written = row - _FIRST_DATA_ROW
    logger.info(f"{tab}: {written} rows written (counted {total})")
    return written


async def _people_chunks(
    state: str, chunk_size: int
) -> AsyncGenerator[list[list[str]], None]:
    async for chunk in people_db.stream_for_state(state, chunk_size):
        yield people_rows.to_rows(chunk)


async def _membership_chunks(
    state: str, chunk_size: int
) -> AsyncGenerator[list[list[str]], None]:
    async for chunk in memberships.stream_for_state(state, chunk_size):
        yield membership_rows.to_rows(chunk)


async def _post_chunks(
    state: str, chunk_size: int
) -> AsyncGenerator[list[list[str]], None]:
    """Paged, not streamed: `list_page_for_state` already exists and posts are a fraction of
    memberships (TX: 3,201 against 5,844)."""
    offset = 0
    while True:
        _, page = await posts_db.list_page_for_state(state, chunk_size, offset)
        if not page:
            return
        yield post_rows.to_rows(page)
        offset += len(page)


async def _jurisdiction_chunks(
    chunk_size: int,
) -> AsyncGenerator[list[list[str]], None]:
    async for chunk in jurisdictions_db.stream_active(ENTRY_LEVELS, chunk_size):
        yield jurisdiction_rows.to_rows(chunk)


async def sync_state(
    state: str, chunk_size: int = memberships.STATE_CHUNK_SIZE
) -> tuple[int | None, int | None, int | None]:
    """Rewrite one state's three tabs. Returns how many rows each got, None for one left alone.

    Streamed, so peak memory tracks `chunk_size` and not the state — states sync concurrently.
    2,000 rows is ~11 MB held and 44,000 cells a request, balancing that against Sheets' 60
    writes a minute.
    """
    people = await _replace_rows(
        people_tab(state),
        people_rows.HEADERS,
        await people_db.count_for_state(state),
        lambda: _people_chunks(state, chunk_size),
    )
    seats = await _replace_rows(
        memberships_tab(state),
        membership_rows.HEADERS,
        await memberships.count_for_state(state),
        lambda: _membership_chunks(state, chunk_size),
    )
    total_posts, _ = await posts_db.list_page_for_state(state, 1, 0)
    posts = await _replace_rows(
        posts_tab(state),
        post_rows.HEADERS,
        total_posts,
        lambda: _post_chunks(state, chunk_size),
    )
    return people, seats, posts


async def sync_jurisdictions(
    chunk_size: int = memberships.STATE_CHUNK_SIZE,
) -> int | None:
    """The dropdown source: every active jurisdiction, every state, one flat tab."""
    return await _replace_rows(
        JURISDICTIONS_TAB,
        jurisdiction_rows.HEADERS,
        await jurisdictions_db.count_active(ENTRY_LEVELS),
        lambda: _jurisdiction_chunks(chunk_size),
    )


async def order_tabs() -> int:
    """Put the tab bar back where it belongs. Returns how many tabs had to move.

    A state whose tabs do not exist yet is simply not placed, and falls in on a later run.
    """
    states = [row["code"] for row in await jurisdictions_db.get_states_with_names()]
    return await asyncio.to_thread(
        sheets.reorder_tabs, entry_sheet.spreadsheet_id(), ordered_tabs(states)
    )
