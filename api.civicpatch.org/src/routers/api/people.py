from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import database
from shared.utils.person_id_utils import resolve_person_id
import shared.utils.name_utils
import uuid

class PersonResolveRequest(BaseModel):
    name: str
    email: str
    jurisdiction_ocdid: str

class BatchPersonRequest(BaseModel):
    name: str
    email: str

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

    @router.post("/resolve")
    async def resolve_person(request: PersonResolveRequest):
        people = await database.get_people_for_jurisdiction(request.jurisdiction_ocdid)
        identities = shared.utils.name_utils.person_list_to_identities(people)
        matches = resolve_person_id(request.name, request.email, people, identities)
        if not matches:
            # No match, generate new UUID
            return {
                "data": {
                    "person_id": uuid.uuid4(),
                    "person": None,
                    "ambiguous": False
                }
            }
        elif len(matches) == 1:
            # Unique match
            return {
                "data": {
                    "person_id": matches[0].get("id"),
                    "person": matches[0],
                    "ambiguous": False
                }
            }
        else:
            # Ambiguous: multiple matches
            return {
                "data": {
                    "person_id": None,
                    "person": matches,
                    "ambiguous": True
                }
            }

    @router.post("/generate-id")
    async def generate_person_id():
        return {
            "data": {
                "person_id": uuid.uuid4()
            }
        }

    return router
