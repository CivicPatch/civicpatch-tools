import math
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from lib.auth import require_route_access
from pydantic import BaseModel
from typing import Optional
import uuid
from schemas.common import Identity, UserRole, RouteCategory

import database.people as database
import database.jurisdictions as jurisdictions_db
import services.change_logs as change_logs
from core.people_edits import PersonPatch, patch_people, PeopleValidationError
from shared.utils.yaml_utils import yaml_dump, yaml_load
import lib.github.api as github_service
import shared.utils.id_utils
from shared.utils.person_id_utils import resolve_people_ids
import shared.utils.name_utils

class BatchPersonRequest(BaseModel):
    id: Optional[str]
    name: str
    email: Optional[str]

class PeopleBatchResolveRequest(BaseModel):
    jurisdiction_ocdid: str
    people: list[BatchPersonRequest]
    with_data: bool = False

class OpenPrRequest(BaseModel):
    jurisdiction_ocdid: str
    data: list[PersonPatch]


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def list_people_endpoint(
        jurisdiction_ocdid: str,
    ):
        people = await database.get_people(
            jurisdiction_ocdid=jurisdiction_ocdid, status=database.ACTIVE_STATUS
        )
        return {
            "data": people
        }

    @router.get("/search")
    async def search_people_endpoint(
        jurisdiction_ocdid: str,
        status: Optional[str] = Query(
            None, description="Filter by people.status — active or inactive"
        ),
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        people = await database.get_person_models(
            jurisdiction_ocdid, status=status
        )
        return {"data": people}

    @router.get("/geo")
    async def list_people_by_geo_endpoint(
        lat: float,
        long: float,
    ):
        people = await jurisdictions_db.get_people_by_geo(lat, long)
        return {
            "data": people
        }
    
    @router.delete("/{person_id}")
    async def delete_person_endpoint(
        person_id: str,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.CONTRIBUTORS)),
    ):
        await database.delete_person(person_id)
        return {"data": None}

    @router.get("/directory")
    async def list_directory_endpoint(
        jurisdiction_ocdid: str,
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        offset = (page - 1) * per_page
        total, people = await database.get_people_page(jurisdiction_ocdid, per_page, offset)
        return {
            "total_items": total,
            "page": page,
            "total_pages": math.ceil(total / per_page) if total > 0 else 1,
            "data": people,
        }

    @router.post("/batch-resolve")
    async def batch_resolve_people_endpoint(
        request: PeopleBatchResolveRequest,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED))
    ):
        people = await database.get_person_models(request.jurisdiction_ocdid)
        identities = shared.utils.name_utils.person_list_to_identities(people)

        people_to_resolve = [p.model_dump() for p in request.people]
        results = resolve_people_ids(people_to_resolve, people, identities)

        if request.with_data:
            people_by_id = {getattr(p, "id", None): p for p in people}
            for result in results:
                if result["person"] is None and result["id"]:
                    result["person"] = people_by_id.get(result["id"])

        return {
            "data": results
        }

    @router.post("/generate-id")
    async def generate_person_id(
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED))
    ):
        return {
            "data": {
                "person_id": uuid.uuid4()
            }
        }

    @router.patch("/data")
    async def patch_people_data_endpoint(
        request: OpenPrRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ):
        folder_path = shared.utils.id_utils.jurisdiction_ocdid_to_folder(request.jurisdiction_ocdid)
        file_path = f"data/{folder_path}.yml"

        request_id = shared.utils.id_utils.make_request_id()

        # The file on `main` is the base: overlay only the edited fields, then validate and
        # normalize.
        raw = await github_service.get_github_file_contents(file_path)
        base = yaml_load(raw) if raw else []
        if not isinstance(base, list):
            base = []
        try:
            patched = patch_people(base, request.data)
        except PeopleValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.failures)

        # Committed to `main`, not opened as a pull request. Approving a scrape already writes
        # straight to open-data, and a maintainer editing by hand is the same act.
        commit_url = await github_service.upsert_github_file(
            branch_name=github_service.DEFAULT_BRANCH,
            file_path=file_path,
            content_str=yaml_dump(patched),
            commit_message=f"Manual edit: {folder_path}",
            author={
                "name": user.display_name or user.email or user.provider_user_id,
                "email": user.email
                or f"{user.provider_user_id}@users.noreply.github.com",
            },
        )
        if not commit_url:
            return JSONResponse(
                {"error": f"Failed to commit {file_path}"}, status_code=500
            )

        # Record the manual edit in the change log: before = the `main` file we patched,
        # after = what was just published. (Best-effort; logging must not fail the edit.)
        if user.user_id:
            await change_logs.record_manual_edits(
                request_id, request.jurisdiction_ocdid, user.user_id, base, patched
            )

        return {"data": {"request_id": request_id, "commit_url": commit_url}}

    return router