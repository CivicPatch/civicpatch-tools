from fastapi import APIRouter, Depends
from utils.auth_utils import require_route_access
from pydantic import BaseModel
from typing import Optional
import uuid
from schemas.common import Identity, RouteCategory

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
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED))
    ):
        people = await database.get_people_for_jurisdiction(request.jurisdiction_ocdid)
        identities = shared.utils.name_utils.person_list_to_identities(people)

        people_to_resolve = [p.model_dump() for p in request.people]
        results = resolve_people_ids(people_to_resolve, people, identities)

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

    return router