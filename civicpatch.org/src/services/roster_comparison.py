"""Roster comparisons: run one from an upload and save it, and read saved runs back."""

import asyncio
import logging

from shared.schemas import Person, RoleConfig
from shared.utils.taxonomy import build_taxonomy

from core.roster_comparison_run import build_comparison, rejected_rows
from database.jurisdictions import get_state_jurisdiction_sets
from database.people import get_rosters_by_jurisdiction
from database.roles import get_roles
import database.roster_comparisons as database
import environment
from core.page_urls import roster_comparison_page_url
from core.roster_comparison_rates import LEVELS_BY_FILTER, worst_first
from schemas.pagination import paginated_response, pagination_offset
from schemas.roster_comparisons import (
    PeopleFilter,
    PersonComparison,
    RejectedRow,
    RosterComparisonCreated,
    RosterComparisonListItem,
    RosterComparisonListPage,
    RosterComparisonRun,
    RosterComparisonSummary,
    RosterComparisonUpload,
    RunPeoplePage,
    UploadedRow,
)

logger = logging.getLogger(__name__)

# Enough to see what went wrong; a large bad upload usually repeats one mistake.
MAX_REJECTED_LISTED = 50


class RowsOutsideState(ValueError):
    """Rows naming no jurisdiction of the upload's state: nothing is saved until they are fixed."""

    def __init__(self, state: str, rejected: list[RejectedRow]):
        self.rejected = rejected
        self.listed = rejected[:MAX_REJECTED_LISTED]
        rows = "; ".join(f"row {row.source_row}: {row.jurisdiction_ocdid} ({row.reason})" for row in self.listed)
        more = f"; and {len(rejected) - len(self.listed)} more" if len(rejected) > len(self.listed) else ""
        super().__init__(
            f"Not saved (the whole upload, or this batch): rows naming no jurisdiction in {state}: "
            f"{len(rejected)}. Find each in {state}'s jurisdictions (list or search by name), fix its "
            f"jurisdiction_ocdid, tell the user which rows failed and what you changed each to, then "
            f"send again. {rows}{more}"
        )


async def check_rows_in_state(state: str, rows: list[UploadedRow], user_id: str) -> set[str]:
    """Returns the state's jurisdiction ocdids; raises RowsOutsideState if any row names another."""
    state_ocdids = (await get_state_jurisdiction_sets(state)).total
    rejected = rejected_rows(rows, state_ocdids, state)
    if rejected:
        # Counts only, no row data: how often agents miss, to judge the instructions by.
        logger.info("roster comparison refused: state=%s user_id=%s rows=%d of %d", state, user_id, len(rejected), len(rows))
        raise RowsOutsideState(state, rejected)
    return state_ocdids


async def run_roster_comparison(upload: RosterComparisonUpload, started_by_user_id: str) -> str:
    """Returns the saved run's id."""
    state_ocdids = await check_rows_in_state(upload.state, upload.rows, started_by_user_id)
    named = sorted({row.jurisdiction_ocdid for row in upload.rows})
    rosters = {
        ocdid: [Person(**person) for person in people]
        for ocdid, people in (await get_rosters_by_jurisdiction(named)).items()
    }
    taxonomy = build_taxonomy(RoleConfig(roles=await get_roles()))
    # Name matching is CPU work: off the event loop, so other requests keep moving.
    comparison = await asyncio.to_thread(build_comparison, upload, state_ocdids, rosters, taxonomy)
    return await database.insert_roster_comparison(started_by_user_id, comparison)


class RunNotFound(LookupError):
    def __init__(self, run_id: str):
        super().__init__(f"No roster comparison {run_id}.")


async def get_run_created(run_id: str) -> RosterComparisonCreated:
    run = await _run(run_id)
    return RosterComparisonCreated(id=run_id, page_url=_page_url(run_id), rates=run.rates)


async def list_runs(page: int, per_page: int) -> RosterComparisonListPage:
    total, rows = await database.get_roster_comparison_runs(per_page, pagination_offset(page, per_page))
    items = [RosterComparisonListItem(**row.model_dump(), page_url=_page_url(row.id)) for row in rows]
    return RosterComparisonListPage.model_validate(paginated_response(total, page, per_page, items))


async def get_run_summary(run_id: str) -> RosterComparisonSummary:
    run = await _run(run_id)
    jurisdictions = await database.get_roster_comparison_jurisdictions(run_id)
    return RosterComparisonSummary(run=run, page_url=_page_url(run_id), jurisdictions=worst_first(jurisdictions))


async def get_run_people(run_id: str, jurisdiction_ocdid: str) -> list[PersonComparison]:
    await _run(run_id)
    return await database.get_roster_comparison_people(run_id, jurisdiction_ocdid)


async def get_run_people_page(run_id: str, people_filter: PeopleFilter, page: int, per_page: int) -> RunPeoplePage:
    await _run(run_id)
    levels = LEVELS_BY_FILTER[people_filter.level] if people_filter.level else []
    total, people = await database.get_roster_comparison_people_page(
        run_id, people_filter.outcome, people_filter.field, levels, per_page, pagination_offset(page, per_page)
    )
    return RunPeoplePage.model_validate(paginated_response(total, page, per_page, people))


async def _run(run_id: str) -> RosterComparisonRun:
    run = await database.get_roster_comparison_run(run_id)
    if run is None:
        raise RunNotFound(run_id)
    return run


def _page_url(run_id: str) -> str:
    return roster_comparison_page_url(environment.instance_url(), run_id)
