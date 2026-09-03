import math
import re
import uuid
from typing import Optional

import database.jurisdictions as jurisdictions_db
import database.people as database
import services.roster_edits as roster_edits
import shared.utils.id_utils
import shared.utils.name_utils
from core.people_edits import PeopleValidationError, PersonPatch
from fastapi import APIRouter, Depends, HTTPException, Query
from lib.auth import require_route_access
from pydantic import BaseModel
from schemas.common import Identity, RouteCategory, UserRole
from shared.utils.person_id_utils import resolve_people_ids


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
        """One jurisdiction's seated roster. Public, because it is the public page's own data.

        Unpaged on purpose: a roster is bounded by how many seats a government has, and the
        largest in the database is eighteen. Bulk reads belong on `/bulk`, which is paged.
        """
        people = await database.get_roster(jurisdiction_ocdid=jurisdiction_ocdid)
        return {"data": people}

    @router.get("/bulk")
    async def bulk_people_endpoint(
        state: str,
        page: int = Query(1, ge=1),
        # Higher than /directory's 20: this is the bulk read, and a state is thousands.
        per_page: int = Query(200, ge=1, le=500),
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        """A whole state's seated roster, paged.

        One request per page instead of one per jurisdiction — Washington is 281 jurisdictions
        and 1,416 seated people. Signed-in rather than public: the same rows are readable a
        jurisdiction at a time, but handing out a state in one call is a different thing to
        offer anonymously.
        """
        if not re.fullmatch(r"[A-Za-z]{2}", state):
            raise HTTPException(
                status_code=400, detail="state must be a two-letter code, e.g. 'wa'"
            )
        total, people = await database.get_roster_page(
            None, state.lower(), per_page, (page - 1) * per_page
        )
        return {
            "total_items": total,
            "page": page,
            "total_pages": math.ceil(total / per_page) if total > 0 else 1,
            "data": people,
        }

    @router.get("/search")
    async def search_people_endpoint(
        jurisdiction_ocdid: str,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        """Everyone we hold here, seated or not.

        The `status` filter is gone with the column it named. Whether somebody currently holds
        a seat is a memberships question, and this endpoint's job is to find a person.
        """
        people = await database.get_person_models(jurisdiction_ocdid)
        return {"data": people}

    @router.get("/geo")
    async def list_people_by_geo_endpoint(
        lat: float,
        long: float,
    ):
        people = await jurisdictions_db.get_people_by_geo(lat, long)
        return {"data": people}

    @router.delete("/{person_id}")
    async def delete_person_endpoint(
        person_id: str,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.CONTRIBUTORS)
        ),
    ):
        # The change log this writes is what the sheet sweep reads; nothing here calls out.
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
        total, people = await database.get_people_page(
            jurisdiction_ocdid, per_page, offset
        )
        return {
            "total_items": total,
            "page": page,
            "total_pages": math.ceil(total / per_page) if total > 0 else 1,
            "data": people,
        }

    @router.post("/batch-resolve")
    async def batch_resolve_people_endpoint(
        request: PeopleBatchResolveRequest,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
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

        return {"data": results}

    @router.post("/generate-id")
    async def generate_person_id(
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        return {"data": {"person_id": uuid.uuid4()}}

    @router.patch("/data")
    async def patch_people_data_endpoint(
        request: OpenPrRequest,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        try:
            changeset_id, _ = await roster_edits.edit_published(
                request.jurisdiction_ocdid, request.data, user
            )
        except PeopleValidationError as exc:
            raise HTTPException(status_code=422, detail=exc.failures)
        except roster_edits.AnonymousEdit:
            raise HTTPException(status_code=401, detail="Sign in to record an edit.")
        except roster_edits.EmptyEdit:
            raise HTTPException(
                status_code=409,
                detail="That edit would leave the jurisdiction with nobody on it.",
            )
        return {"data": {"changeset_id": changeset_id}}

    return router
