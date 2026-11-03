"""Roster comparisons: run one from an upload and save it, and read saved runs back."""

import asyncio
import logging

from shared.schemas import Person, RoleConfig
from shared.utils.taxonomy import build_taxonomy

from core.roster_comparison_jurisdictions import ocdids_of, resolve_rows
from core.roster_comparison_refusal import MAX_REJECTED_LISTED, refusal_message
from core.roster_comparison_run import build_comparison
import database.organizations as organizations_db
from database.database import get_pool
from database.jurisdictions import get_state_jurisdictions
from database.people import get_rosters_by_jurisdiction
from database.roles import get_roles
import database.roster_comparisons as database
import environment
from core.page_urls import roster_comparison_page_url
from core.roster_comparison_rates import LEVELS_BY_FILTER, compared_organizations, with_not_compared, worst_first
from core.roster_comparison_report import report_markdown
from schemas.jurisdictions import StateJurisdiction
from schemas.pagination import paginated_response, pagination_offset
from schemas.roster_comparisons import (
    IncomingRow,
    PeopleFilter,
    PersonComparison,
    RejectedRow,
    ResolvedUpload,
    RosterComparisonCreated,
    RosterComparisonListItem,
    RosterComparisonListPage,
    RosterComparisonReport,
    RosterComparisonRun,
    RosterComparisonSummary,
    RosterComparisonUpload,
    RunJurisdiction,
    RunPeoplePage,
    UploadedRow,
)

logger = logging.getLogger(__name__)

class RowsOutsideState(ValueError):
    """Rows with no single jurisdiction in the upload's state: nothing is saved until they are fixed."""

    def __init__(self, state: str, rejected: list[RejectedRow]):
        self.rejected = rejected
        self.listed = rejected[:MAX_REJECTED_LISTED]
        super().__init__(refusal_message(state, rejected))


async def resolve_incoming_rows(
    state: str, rows: list[IncomingRow], jurisdictions: list[StateJurisdiction], user_id: str
) -> list[UploadedRow]:
    """Raises RowsOutsideState if any row has no single jurisdiction in the state."""
    # Name matching is CPU work: off the event loop, so other requests keep moving.
    resolved, rejected = await asyncio.to_thread(resolve_rows, rows, jurisdictions, state)
    if rejected:
        # Counts only, no row data: how often agents miss, to judge the instructions by.
        logger.info("roster comparison refused: state=%s user_id=%s rows=%d of %d", state, user_id, len(rejected), len(rows))
        raise RowsOutsideState(state, rejected)
    return resolved


async def run_roster_comparison(upload: RosterComparisonUpload, started_by_user_id: str) -> str:
    """Returns the saved run's id."""
    jurisdictions = await get_state_jurisdictions(upload.state, upload.level)
    rows = await resolve_incoming_rows(upload.state, upload.rows, jurisdictions, started_by_user_id)
    resolved_upload = ResolvedUpload(**upload.model_dump(exclude={"rows"}), rows=rows)
    return await compare_and_save(resolved_upload, ocdids_of(jurisdictions), started_by_user_id)


async def compare_and_save(upload: ResolvedUpload, state_ocdids: set[str], started_by_user_id: str) -> str:
    """Returns the saved run's id."""
    named = sorted({row.jurisdiction_ocdid for row in upload.rows})
    rosters = {
        ocdid: [Person(**person) for person in people]
        for ocdid, people in (await get_rosters_by_jurisdiction(named)).items()
    }
    taxonomy = build_taxonomy(RoleConfig(roles=await get_roles()))
    organization_names = await _organization_names(rosters)
    # Name matching is CPU work: off the event loop, so other requests keep moving.
    comparison = await asyncio.to_thread(
        build_comparison, upload, state_ocdids, rosters, taxonomy, organization_names
    )
    return await database.insert_roster_comparison(started_by_user_id, comparison)


async def _organization_names(rosters: dict[str, list[Person]]) -> dict[str, str]:
    ids = sorted(
        {
            membership.organization_id
            for people in rosters.values()
            for person in people
            for membership in person.memberships
            if membership.organization_id
        }
    )
    pool = await get_pool()
    async with pool.connection() as conn, conn.cursor() as cur:
        return await organizations_db.names(cur, ids)


class RunNotFound(LookupError):
    def __init__(self, run_id: str):
        super().__init__(f"No roster comparison {run_id}.")


async def get_run_created(run_id: str) -> RosterComparisonCreated:
    """The rates as the summary counts them by default, so the agent's first report matches the page."""
    summary = await get_run_summary(run_id, None)
    return RosterComparisonCreated(
        id=run_id, page_url=summary.page_url, rates=summary.run.rates, markdown=await _report_of(summary)
    )


async def list_runs(page: int, per_page: int) -> RosterComparisonListPage:
    total, rows = await database.get_roster_comparison_runs(per_page, pagination_offset(page, per_page))
    items = [RosterComparisonListItem(**row.model_dump(), page_url=_page_url(row.id)) for row in rows]
    return RosterComparisonListPage.model_validate(paginated_response(total, page, per_page, items))


async def get_run_summary(run_id: str, organizations: list[str] | None) -> RosterComparisonSummary:
    run = await _run(run_id)
    run_organizations = await database.get_roster_comparison_organizations(run_id)
    compared = compared_organizations(organizations, run_organizations)
    not_compared = await database.count_roster_comparison_not_compared(run_id, compared)
    jurisdictions = [
        jurisdiction.model_copy(
            update={"rates": with_not_compared(jurisdiction.rates, not_compared.get(jurisdiction.jurisdiction_ocdid, 0))}
        )
        for jurisdiction in await database.get_roster_comparison_jurisdictions(run_id)
    ]
    return RosterComparisonSummary(
        run=run.model_copy(update={"rates": with_not_compared(run.rates, sum(not_compared.values()))}),
        page_url=_page_url(run_id),
        jurisdictions=worst_first(jurisdictions),
        organizations=run_organizations,
        compared_organizations=compared,
        nickname_matches=await database.get_roster_comparison_nickname_matches(run_id),
    )


async def get_run_report(run_id: str, organizations: list[str] | None) -> RosterComparisonReport:
    summary = await get_run_summary(run_id, organizations)
    return RosterComparisonReport(markdown=await _report_of(summary))


async def _report_of(summary: RosterComparisonSummary) -> str:
    jurisdictions = await get_run_jurisdictions(summary.run.id, True)
    names = {jurisdiction.jurisdiction_ocdid: jurisdiction.name for jurisdiction in jurisdictions}
    return report_markdown(summary, names)


async def get_run_jurisdictions(run_id: str, compared: bool | None) -> list[RunJurisdiction]:
    run = await _run(run_id)
    return await database.get_roster_comparison_run_jurisdictions(run_id, run.state, run.level, compared)


async def get_run_people(
    run_id: str, jurisdiction_ocdid: str, organizations: list[str] | None
) -> list[PersonComparison]:
    await _run(run_id)
    compared = await _compared(run_id, organizations)
    return await database.get_roster_comparison_people(run_id, jurisdiction_ocdid, compared)


async def get_run_people_page(
    run_id: str, people_filter: PeopleFilter, organizations: list[str] | None, page: int, per_page: int
) -> RunPeoplePage:
    await _run(run_id)
    levels = LEVELS_BY_FILTER[people_filter.level] if people_filter.level else []
    total, people = await database.get_roster_comparison_people_page(
        run_id,
        people_filter.outcome,
        people_filter.field,
        levels,
        await _compared(run_id, organizations),
        per_page,
        pagination_offset(page, per_page),
    )
    return RunPeoplePage.model_validate(paginated_response(total, page, per_page, people))


async def _compared(run_id: str, organizations: list[str] | None) -> list[str]:
    return compared_organizations(organizations, await database.get_roster_comparison_organizations(run_id))


async def _run(run_id: str) -> RosterComparisonRun:
    run = await database.get_roster_comparison_run(run_id)
    if run is None:
        raise RunNotFound(run_id)
    return run


def _page_url(run_id: str) -> str:
    return roster_comparison_page_url(environment.instance_url(), run_id)
