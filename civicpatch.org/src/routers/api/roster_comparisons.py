"""Roster comparisons: an agent uploads a state's officials, converted to one shape; civicpatch
compares them with its own roster and keeps the run. Maintainers and above."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

import services.roster_comparison as service
import services.roster_comparison_drafts as drafts
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory, UserRole
from schemas.roster_comparisons import (
    ComparedField,
    CreatedResponse,
    DraftResponse,
    DraftRows,
    FieldFilter,
    FieldPeoplePage,
    PeopleResponse,
    RosterComparisonHeader,
    RosterComparisonListPage,
    RosterComparisonUpload,
    SummaryResponse,
)

# Enforced by `lib.body_limit.PathBodyLimit` in main.py, before the body is read.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
UPLOAD_PATH = "/api/v1/roster-comparisons"


def _maintainer() -> Identity:
    return Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS))


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("", response_model=CreatedResponse)
    async def create_roster_comparison_endpoint(
        upload: RosterComparisonUpload, user: Identity = _maintainer()
    ) -> dict:
        """Compare an uploaded roster with civicpatch's and keep the run. Convert the user's file
        to this shape first; send it as the JSON body (`curl --data-binary @file.json`)."""
        run_id = await service.run_roster_comparison(upload, _owner(user))
        return {"data": await _or_404(service.get_run_created(run_id))}

    @router.post("/drafts", response_model=DraftResponse)
    async def start_roster_comparison_draft_endpoint(
        header: RosterComparisonHeader, user: Identity = _maintainer()
    ) -> dict:
        """Start an upload sent in batches: everything but the rows. For agents that cannot send
        the whole file in one request; the draft is yours alone and expires after a day."""
        return {"data": await drafts.start_draft(header, _owner(user))}

    @router.post("/drafts/{draft_id}/rows", response_model=DraftResponse)
    async def add_roster_comparison_draft_rows_endpoint(
        draft_id: uuid.UUID, batch: DraftRows, user: Identity = _maintainer()
    ) -> dict:
        """Add one batch of rows to a draft."""
        return {"data": await _draft_errors(drafts.add_draft_rows(str(draft_id), batch.rows, _owner(user)))}

    @router.post("/drafts/{draft_id}/finish", response_model=CreatedResponse)
    async def finish_roster_comparison_draft_endpoint(draft_id: uuid.UUID, user: Identity = _maintainer()) -> dict:
        """Compare the draft's rows and keep the run, as a one-shot upload would; the draft is gone after."""
        return {"data": await _draft_errors(drafts.finish_draft(str(draft_id), _owner(user)))}

    @router.get("", response_model=RosterComparisonListPage)
    async def list_roster_comparisons_endpoint(
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        _: Identity = _maintainer(),
    ):
        """Saved runs, newest first, each with its page."""
        return await service.list_runs(page, per_page)

    @router.get("/{run_id}", response_model=SummaryResponse)
    async def get_roster_comparison_endpoint(run_id: uuid.UUID, _: Identity = _maintainer()) -> dict:
        """A run's rates for the state and each jurisdiction, most unmatched first."""
        return {"data": await _or_404(service.get_run_summary(str(run_id)))}

    @router.get("/{run_id}/jurisdictions/{jurisdiction_ocdid:path}", response_model=PeopleResponse)
    async def get_roster_comparison_jurisdiction_endpoint(
        run_id: uuid.UUID, jurisdiction_ocdid: str, _: Identity = _maintainer()
    ) -> dict:
        """One jurisdiction's people: uploaded rows with their outcome, field levels and warnings,
        then civicpatch's people no row matched."""
        return {"data": await _or_404(service.get_run_people(str(run_id), jurisdiction_ocdid))}

    @router.get("/{run_id}/fields/{field}", response_model=FieldPeoplePage)
    async def get_roster_comparison_field_endpoint(
        run_id: uuid.UUID,
        field: ComparedField,
        level: FieldFilter,
        page: int = Query(1, ge=1),
        per_page: int = Query(50, ge=1, le=200),
        _: Identity = _maintainer(),
    ):
        """The matched people behind one field's conflict or one-side-has-more count, paged."""
        return await _or_404(service.get_run_field_page(str(run_id), field, level, page, per_page))

    return router


def _owner(user: Identity) -> str:
    if not user.user_id:
        raise HTTPException(status_code=401, detail="User ID not available")
    return user.user_id


async def _draft_errors(call):
    try:
        return await call
    except drafts.DraftNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except drafts.DraftTooLarge as error:
        raise HTTPException(status_code=413, detail=str(error)) from error
    except drafts.DraftIsEmpty as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


async def _or_404(read):
    try:
        return await read
    except service.RunNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
