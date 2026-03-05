from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import database

from shared.utils.person_id_utils import resolve_person_id
import shared.utils.name_utils
import uuid

class BatchPersonRequest(BaseModel):
    name: str
    email: Optional[str]

class PeopleBatchResolveRequest(BaseModel):
    jurisdiction_ocdid: str
    people: list[BatchPersonRequest]


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/batch-resolve")
    async def batch_resolve_people_endpoint(request: PeopleBatchResolveRequest):
        people = await database.get_people_for_jurisdiction(request.jurisdiction_ocdid)
        identities = shared.utils.name_utils.person_list_to_identities(people)

        results = []
        for person in request.people:
            matches = resolve_person_id(person.name, person.email, people, identities)
            if not matches:
                results.append({
                    "id": uuid.uuid4(),
                    "person": None,
                    "ambiguous": False
                })
            elif len(matches) == 1:
                results.append({
                    "id": matches[0].id,
                    "person": matches[0],
                    "ambiguous": False
                })
            else:
                results.append({
                    "id": ":".join(m.id for m in matches),
                    "person": matches,
                    "ambiguous": True
                })

        return {
            "data": results
        }

    @router.post("/generate-id")
    async def generate_person_id():
        return {
            "data": {
                "person_id": uuid.uuid4()
            }
        }

    return router
