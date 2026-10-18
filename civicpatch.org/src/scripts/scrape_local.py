"""Scrape named jurisdictions on the local pipelines server, a few at a time. Dev only.

Starts each run the way the trigger endpoint does (register, then the Temporal workflow), with
the jurisdiction's name and url from the database. Every local run shares one container, and
past two at a time the devbox runs out of memory (33 at once froze it), so this queues the rest.
One line per event: STARTED, FINISHED, SKIPPED, WAITING_MEMORY, PROGRESS, STOPPED, DONE.

    docker exec -w /app civicpatch-org python src/scripts/scrape_local.py ocd-jurisdiction/country:us/state:me/county:aroostook/government
    mise run scrape-local -- ocd-jurisdiction/country:us/state:me/county:aroostook/government
"""

import argparse
import asyncio
import sys
import time

from pydantic import BaseModel

import lib.temporal.client as temporal_service
import shared.utils.id_utils
from database.database import get_pool
from database.pipeline_runs import register_run
from database.review_pool import has_open_review
from routers.api.pipeline_runs import _DISPATCH_MODE_LOCAL, DISPATCH_MODE
from shared.utils.statuses import PipelineRunKind, PipelineRunStatus

MEMINFO_PATH = "/proc/meminfo"
MEMINFO_AVAILABLE_KEY = "MemAvailable:"
DEFAULT_MAX_IN_FLIGHT = 2
MIN_AVAILABLE_GIB = 3.0
POLL_SECONDS = 15
PROGRESS_SECONDS = 300
MAX_CONSECUTIVE_ERRORS = 3


class Run(BaseModel):
    run_id: str
    jurisdiction_ocdid: str


class RunState(BaseModel):
    status: str
    finished: bool
    progress: int


def available_gib(meminfo: str) -> float:
    for line in meminfo.splitlines():
        if line.startswith(MEMINFO_AVAILABLE_KEY):
            return int(line.split()[1]) / 1024 / 1024
    raise ValueError(f"{MEMINFO_AVAILABLE_KEY} missing from meminfo")


def read_available_gib() -> float:
    with open(MEMINFO_PATH) as meminfo:
        return available_gib(meminfo.read())


def emit(event: str, *parts: str) -> None:
    print(time.strftime("%H:%M:%S"), event, *parts, flush=True)


async def in_flight_runs() -> list[Run]:
    """Runs already going count against the cap, so a second invocation cannot overshoot it."""
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT id::text, jurisdiction_ocdid FROM pipeline_runs WHERE finished_at IS NULL")
        return [Run(run_id=row[0], jurisdiction_ocdid=row[1]) for row in await cur.fetchall()]


async def run_states(runs: list[Run]) -> dict[str, RunState]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT id::text, status, finished_at IS NOT NULL, coalesce(progress, 0)"
            " FROM pipeline_runs WHERE id::text = ANY(%s)",
            ([run.run_id for run in runs],),
        )
        return {row[0]: RunState(status=row[1], finished=row[2], progress=row[3]) for row in await cur.fetchall()}


async def name_and_url(ocdid: str) -> tuple[str | None, str | None]:
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("SELECT name, url FROM jurisdictions WHERE jurisdiction_ocdid = %s", (ocdid,))
        row = await cur.fetchone()
        return (row[0], row[1]) if row else (None, None)


async def start_run(ocdid: str, name: str | None, url: str) -> Run:
    run_id = shared.utils.id_utils.make_id()
    await register_run(
        run_id=run_id,
        kind=PipelineRunKind.PEOPLE_COLLECTOR,
        arguments_json={"jurisdiction_ocdid": ocdid, "name": name, "url": url, "source_urls": None},
        jurisdiction_ocdid=ocdid,
    )
    await temporal_service.start_people_collector_workflow(
        jurisdiction_ocdid=ocdid, pipeline_run_id=run_id, dispatch_mode=DISPATCH_MODE, url=url
    )
    return Run(run_id=run_id, jurisdiction_ocdid=ocdid)


async def start_next(ocdid: str, supersede: bool) -> Run | None:
    """Start one jurisdiction, or say why not. None means skipped."""
    if not supersede and await has_open_review(ocdid):
        emit("SKIPPED", "open review (pass --supersede to start anyway)", ocdid)
        return None
    name, url = await name_and_url(ocdid)
    if not url:
        emit("SKIPPED", "no url", ocdid)
        return None
    run = await start_run(ocdid, name, url)
    emit("STARTED", ocdid)
    return run


async def finished_runs(in_flight: list[Run]) -> list[tuple[Run, RunState]]:
    states = await run_states(in_flight) if in_flight else {}
    return [(run, states[run.run_id]) for run in in_flight if run.run_id in states and states[run.run_id].finished]


def progress_line(in_flight: list[Run], states: dict[str, RunState]) -> str:
    return ", ".join(
        f"{run.jurisdiction_ocdid} {states[run.run_id].progress}%" if run.run_id in states
        else run.jurisdiction_ocdid
        for run in in_flight
    ) or "none"


async def scrape(queue: list[str], max_in_flight: int, supersede: bool) -> None:
    in_flight = await in_flight_runs()
    consecutive_errors = 0
    last_progress = time.monotonic()
    while queue or in_flight:
        for run, state in await finished_runs(in_flight):
            in_flight.remove(run)
            emit("FINISHED", state.status, run.jurisdiction_ocdid)
            consecutive_errors = consecutive_errors + 1 if state.status == PipelineRunStatus.ERROR else 0
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            emit("STOPPED", f"{consecutive_errors} errors in a row, not starting more")
            return
        if queue and len(in_flight) < max_in_flight:
            if read_available_gib() < MIN_AVAILABLE_GIB:
                emit("WAITING_MEMORY", f"{read_available_gib():.1f}GiB available")
            else:
                started = await start_next(queue.pop(0), supersede)
                in_flight += [started] if started else []
                continue
        if in_flight and time.monotonic() - last_progress >= PROGRESS_SECONDS:
            emit("PROGRESS", progress_line(in_flight, await run_states(in_flight)), f"| {len(queue)} queued")
            last_progress = time.monotonic()
        await asyncio.sleep(POLL_SECONDS)
    emit("DONE")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("jurisdictions", nargs="+", help="jurisdiction ocdids")
    parser.add_argument("--max-in-flight", type=int, default=DEFAULT_MAX_IN_FLIGHT)
    parser.add_argument("--supersede", action="store_true", help="start even where a scrape awaits review")
    args = parser.parse_args()
    if DISPATCH_MODE != _DISPATCH_MODE_LOCAL:
        sys.exit(f"Dev only: dispatch mode is {DISPATCH_MODE!r}, which would start real remote runs.")
    asyncio.run(scrape(list(args.jurisdictions), args.max_in_flight, args.supersede))


if __name__ == "__main__":
    main()
