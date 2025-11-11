import os
import yaml
import urllib
from fastapi import APIRouter, HTTPException, Security

import civicpatch.id_utils
import database
import github_service
import services.auth as AuthService
from schemas import Jurisdiction

VALID_STATES = [
    "al",
    "ak",
    "az",
    "ar",
    "ca",
    "co",
    "ct",
    "de",
    "fl",
    "ga",
    "hi",
    "id",
    "il",
    "in",
    "ia",
    "ks",
    "ky",
    "la",
    "me",
    "md",
    "ma",
    "mi",
    "mn",
    "ms",
    "mo",
    "mt",
    "ne",
    "nv",
    "nh",
    "nj",
    "nm",
    "ny",
    "nc",
    "nd",
    "oh",
    "ok",
    "or",
    "pa",
    "ri",
    "sc",
    "sd",
    "tn",
    "tx",
    "ut",
    "vt",
    "va",
    "wa",
    "wv",
    "wi",
    "wy",
]

GITHUB_WORKFLOW_TOKEN = os.getenv("GITHUB_WORKFLOW_TOKEN")


def get_router(api_key_header) -> APIRouter:
    router = APIRouter()

    @router.get("/available")
    async def list_available_jurisdictions_endpoint(
        state: str,
        num_jurisdictions: int = 10,
        authorization: str = Security(api_key_header),
    ):
        if not authorization and not authorization.strip():
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        if state.lower() not in VALID_STATES:
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        _server_detail, error_string = await AuthService.is_authorized(authorization)
        if error_string:
            raise HTTPException(status_code=401, detail=error_string)
        jurisdictions_file_content = github_service.get_github_file_contents(
            f"data_source/{state}/jurisdictions_metadata.yml"
        )
        if jurisdictions_file_content is None:
            raise HTTPException(
                status_code=404, detail="Could not find jurisdictions file"
            )

        open_pull_requests = github_service.get_open_pull_requests(
            GITHUB_WORKFLOW_TOKEN
        )
        jurisdictions_data = yaml.safe_load(jurisdictions_file_content)
        jurisdictions = [
            Jurisdiction(
                id=j["jurisdiction"]["id"],
                name=j["jurisdiction"]["name"],
                url=j["jurisdiction"]["url"],
            )
            for j in jurisdictions_data["jurisdictions_by_id"].values()
            if j["jurisdiction"].get("url") and not j.get("updated_at")
        ]
        open_pull_request_ids = [pr.jurisdiction_id for pr in open_pull_requests]

        filtered_jurisdictions = [
            j for j in jurisdictions if j.id not in open_pull_request_ids
        ][:num_jurisdictions]
        return {"jurisdictions": filtered_jurisdictions}

    @router.get("/states")
    async def get_jurisdiction_states_endpoint(
        authorization: str = Security(api_key_header),
    ):
        if not authorization and not authorization.strip():
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        _server_detail, error_string = await AuthService.is_authorized(authorization)
        if error_string:
            raise HTTPException(status_code=403, detail=error_string)

        states = await database.get_jurisdiction_states()

        return {"total_items": len(states), "data": states}

    @router.get("/{jurisdiction_ocdid_slug}")
    async def get_jurisdiction_data_endpoint(
        jurisdiction_ocdid_slug: str,
        authorization: str = Security(api_key_header),
    ):
        if not authorization and not authorization.strip():
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        _server_detail, error_string = await AuthService.is_authorized(authorization)
        if error_string:
            raise HTTPException(status_code=403, detail=error_string)

        jurisdiction_ocdid = civicpatch.id_utils.slug_to_jurisdiction_id(
            jurisdiction_ocdid_slug
        )
        jurisdiction_data = await database.get_jurisdiction(jurisdiction_ocdid)

        return {"data": jurisdiction_data}

    @router.get("/{state}/search")
    async def get_jurisdictions_search_endpoint(
        state: str,
        search_string: str = "",
        limit: int = 0,
        page: int = 1,
        authorization: str = Security(api_key_header),
    ):
        if not authorization and not authorization.strip():
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        _server_detail, error_string = await AuthService.is_authorized(authorization)
        if error_string:
            raise HTTPException(status_code=403, detail=error_string)

        skip = (page - 1) * limit

        total_items, jurisdictions = await database.search_jurisdictions(
            state, search_string, limit, skip
        )

        next_skip = skip + len(jurisdictions)
        next_link = ""
        prev_link = ""

        if page > 1:
            query_params = urllib.parse.urlencode({"limit": limit, "page": page - 1})
            prev_link = f"/api/jurisdictions/{state}/search?{query_params}"

        if next_skip < total_items:
            query_params = urllib.parse.urlencode({"limit": limit, "page": page + 1})
            next_link = f"/api/jurisdictions/{state}/search?{query_params}"

        self_query_params = urllib.parse.urlencode({"limit": limit, "page": page})
        self_link = f"/api/jurisdictions/{state}/search?{self_query_params}"

        return {
            "total_items": total_items,
            "page": page,
            "total_pages": (total_items + limit - 1) // limit if limit > 0 else 1,
            "limit": limit,
            "data": jurisdictions,
            "links": {"prev": prev_link, "next": next_link, "self": self_link},  # TODO!
        }

    @router.get("/{jurisdiction_ocdid_slug}/people")
    async def get_jurisdiction_people_endpoint(
        jurisdiction_ocdid_slug: str,
        authorization: str = Security(api_key_header),
    ):
        if not authorization and not authorization.strip():
            raise HTTPException(status_code=401, detail="Missing Authorization header")

        _server_detail, error_string = await AuthService.is_authorized(authorization)
        if error_string:
            raise HTTPException(status_code=403, detail=error_string)

        jurisdiction_ocdid = civicpatch.id_utils.slug_to_jurisdiction_id(
            jurisdiction_ocdid_slug
        )
        people = await database.get_jurisdiction_people(jurisdiction_ocdid)

        return {
            "total_items": len(people),
            "data": people,
        }

    return router
