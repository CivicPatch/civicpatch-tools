import math
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from lib.auth import require_route_access
from pydantic import BaseModel
from typing import Optional
import uuid
from schemas.common import Identity, Role, RouteCategory

import database.people as database
import database.jurisdictions as jurisdictions_db
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
    data: list[dict]


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def list_people_endpoint(
        jurisdiction_ocdid: str,
    ):
        people = await database.get_jurisdiction_people(jurisdiction_ocdid)
        return {
            "data": people
        }

    @router.get("/search")
    async def search_people_endpoint(
        jurisdiction_ocdid: str,
        state: Optional[str] = Query(None, description="Filter by state"),
        name: Optional[str] = Query(None, description="Filter by name"),
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])),
    ):
        people = await database.get_people_for_jurisdiction(jurisdiction_ocdid, status=state)

        if name is None:
            return {"data": people}

        matches = [
            p for p in people
            if shared.utils.name_utils.fuzzy_match(name, p.name)
            or shared.utils.name_utils.exact_match(name, p.name)
            or shared.utils.name_utils.last_name_match(name, p.name)
            or any(
                shared.utils.name_utils.fuzzy_match(name, alias)
                or shared.utils.name_utils.last_name_match(name, alias)
                for alias in (getattr(p, "other_names", None) or [])
            )
        ]
        return {"data": matches}

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
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.CONTRIBUTORS])),
    ):
        await database.delete_person(person_id)
        return {"data": None}

    @router.get("/directory")
    async def list_directory_endpoint(
        jurisdiction_ocdid: str,
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])),
    ):
        offset = (page - 1) * per_page
        total, people = await database.get_all_people_for_jurisdiction(jurisdiction_ocdid, per_page, offset)
        return {
            "total_items": total,
            "page": page,
            "total_pages": math.ceil(total / per_page) if total > 0 else 1,
            "data": people,
        }

    @router.post("/batch-resolve")
    async def batch_resolve_people_endpoint(
        request: PeopleBatchResolveRequest,
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT]))
    ):
        people = await database.get_people_for_jurisdiction(request.jurisdiction_ocdid)
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
        _: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT]))
    ):
        return {
            "data": {
                "person_id": uuid.uuid4()
            }
        }

    @router.patch("/data")
    async def patch_people_data_endpoint(
        request: OpenPrRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.CONTRIBUTORS])),
    ):
        folder_path = shared.utils.id_utils.jurisdiction_ocdid_to_folder(request.jurisdiction_ocdid)
        file_path = f"data/{folder_path}.yml"

        request_id = shared.utils.id_utils.make_request_id()
        branch_name = shared.utils.id_utils.make_git_branch(request.jurisdiction_ocdid, request_id)

        branch_error = await github_service.create_branch(branch_name)
        if branch_error:
            return JSONResponse({"error": f"Failed to create branch: {branch_error}"}, status_code=500)

        committed = await github_service.update_pull_request_file(
            branch_name=branch_name,
            file_path=file_path,
            new_data=request.data,
            commit_message=f"Manual edit by {user.email}",
        )
        if not committed:
            return JSONResponse({"error": "Failed to commit file update"}, status_code=500)

        pr_number, pr_url = await github_service.create_pull_request(
            branch_name=branch_name,
            title=f"Manual edit: {folder_path}",
            body=f"Manual data edit for `{file_path}`.\n\nEdited by {user.email}.",
        )
        if pr_number is None:
            return JSONResponse({"error": f"Failed to open PR: {pr_url}"}, status_code=500)

        return {"data": {"request_id": request_id, "pr_number": pr_number, "pr_url": pr_url}}

    return router