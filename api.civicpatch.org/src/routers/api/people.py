from fastapi import APIRouter, Depends, Query
from utils.auth_utils import require_route_access
from pydantic import BaseModel
from typing import Optional
import uuid
from schemas.common import Identity, Role, RouteCategory

import database.database as database
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
                for alias in (p.other_names or [])
            )
        ]
        return {"data": matches}

    @router.get("/geo")
    async def list_people_by_geo_endpoint(
        lat: float,
        long: float,
    ):
        people = await database.get_people_by_geo(lat, long)
        return {
            "data": people
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
            people_by_id = {p.id: p for p in people}
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

    return router