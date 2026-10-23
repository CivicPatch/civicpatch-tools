"""Roster comparisons: run one from an upload and save it, and read saved runs back."""

import asyncio

from shared.schemas import Person, RoleConfig
from shared.utils.taxonomy import build_taxonomy

from core.roster_comparison_run import build_comparison
from database.jurisdictions import get_state_jurisdiction_sets
from database.people import get_rosters_by_jurisdiction
from database.roles import get_roles
import database.roster_comparisons as database
import environment
from core.page_urls import roster_comparison_page_url
from core.roster_comparison_rates import LEVELS_BY_FILTER, worst_first
from schemas.pagination import paginated_response, pagination_offset
from schemas.roster_comparisons import (
    ComparedField,
    FieldFilter,
    FieldPeoplePage,
    PersonComparison,
    RosterComparisonCreated,
    RosterComparisonListItem,
    RosterComparisonListPage,
    RosterComparisonRun,
    RosterComparisonSummary,
    RosterComparisonUpload,
)


async def run_roster_comparison(upload: RosterComparisonUpload, started_by_user_id: str) -> str:
    """Returns the saved run's id."""
    state_ocdids = (await get_state_jurisdiction_sets(upload.state)).total
    named = sorted({row.jurisdiction_ocdid for row in upload.rows} & state_ocdids)
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


async def get_run_field_page(
    run_id: str, field: ComparedField, level: FieldFilter, page: int, per_page: int
) -> FieldPeoplePage:
    await _run(run_id)
    total, people = await database.get_roster_comparison_field_people(
        run_id, field, LEVELS_BY_FILTER[level], per_page, pagination_offset(page, per_page)
    )
    return FieldPeoplePage.model_validate(paginated_response(total, page, per_page, people))


async def _run(run_id: str) -> RosterComparisonRun:
    run = await database.get_roster_comparison_run(run_id)
    if run is None:
        raise RunNotFound(run_id)
    return run


def _page_url(run_id: str) -> str:
    return roster_comparison_page_url(environment.instance_url(), run_id)
