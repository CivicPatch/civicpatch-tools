import re
import uuid
from typing import Optional

import database.jurisdictions as jurisdictions_db
import database.people as database
import shared.utils.id_utils
import shared.utils.name_utils
from fastapi import APIRouter, Depends, HTTPException, Query
from lib.auth import require_route_access
from pydantic import BaseModel
from schemas.common import Identity, RouteCategory
from schemas.pagination import paginated_response, pagination_offset
from services.assertions import assertions_for_people
from shared.utils.person_id_utils import resolve_people_ids


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
        """One jurisdiction's seated roster. Public, because it is the public page's own data.

        Unpaged on purpose: a roster is bounded by how many seats a government has, and the
        largest in the database is eighteen. Bulk reads belong on `/bulk`, which is paged.
        """
        people = await database.get_roster(jurisdiction_ocdid=jurisdiction_ocdid)
        return {"data": people}

    @router.get("/assertions")
    async def list_assertions_endpoint(
        jurisdiction_ocdid: str,
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        """Every assertion on this jurisdiction's seated roster, keyed by person id.

        Its own route rather than a field on `GET ""`, which is public: an assertion carries
        `created_by_name`, so folding it in would tell anonymous visitors who edited which
        field of which official. Signed-in only, and the page asks for it only where the
        editor is offered.
        """
        people = await database.get_roster(jurisdiction_ocdid=jurisdiction_ocdid)
        return {
            "data": await assertions_for_people(
                [person["id"] for person in people if person.get("id")]
            )
        }

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
            None, state.lower(), per_page, pagination_offset(page, per_page)
        )
        return paginated_response(total, page, per_page, people)

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

    @router.get("/directory")
    async def list_directory_endpoint(
        jurisdiction_ocdid: str,
        page: int = Query(1, ge=1),
        per_page: int = Query(20, ge=1, le=100),
        _: Identity = Depends(require_route_access(RouteCategory.AUTHENTICATED)),
    ):
        total, people = await database.get_people_page(
            jurisdiction_ocdid, per_page, pagination_offset(page, per_page)
        )
        return paginated_response(total, page, per_page, people)

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

    return router
