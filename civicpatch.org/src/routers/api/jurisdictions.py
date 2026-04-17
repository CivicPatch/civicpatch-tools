import urllib.parse

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import core.jurisdiction_pull_request as jurisdiction_pr_service
import core.jurisdiction_scrape_candidate as candidate_service
import database.jurisdictions as database
import shared.utils.config_utils as config_utils
from lib.auth import require_route_access
from lib.github.pr import PrAuthor
from schemas.common import Identity, Role, RouteCategory
from schemas.requests import JurisdictionsByOcdidsRequest


class PatchJurisdictionDataRequest(BaseModel):
    jurisdiction_ocdid: str
    url: str | None = None
    geoid: str | None = None
    population: int | None = None

def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def get_jurisdiction_data_endpoint(
        jurisdiction_ocdid: str = Query(..., description="The OCD ID of the jurisdiction"),
        with_geom: bool = False,
    ):
        jurisdiction_data = await database.get_jurisdiction(jurisdiction_ocdid, with_geom)

        if jurisdiction_data is None or jurisdiction_data.get("data") is None:
            raise HTTPException(status_code=404, detail="Jurisdiction not found")

        response = {
            "data": jurisdiction_data["data"],
        }

        if with_geom:
            response["geo_center"] = jurisdiction_data.get("geo_center")

        return response

    @router.get("/available")
    async def list_available_jurisdictions_endpoint(
        state: str,
        num_jurisdictions: int = 10,
    ):
        try:
            candidates = await candidate_service.get_scrape_candidates(state, num_jurisdictions)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        return {"jurisdictions": candidates}

    @router.get("/states")
    async def get_jurisdiction_states_endpoint(
    ):
        states = config_utils.get_states()

        return {"total_items": len(states), "data": states}
    
    @router.get("/geojson")
    async def get_geojson_by_point_endpoint(
        lat: float,
        long: float,
        zoom: int | None = None,
    ):
        """
        Return a GeoJSON FeatureCollection of matching geometries near the given point.
        Each Feature includes properties.jurisdiction_ocdid and properties.geoid.
        The optional zoom parameter narrows the search radius for client tiled requests.
        """
        try:
            results = await database.get_geojson_by_latlong(lat, long, zoom)
        except Exception as e:
            raise HTTPException(status_code=500, detail="Database error")

        features = []
        for item in results.get("results", []):
            features.append(
                {
                    "type": "Feature",
                    "properties": {
                        "jurisdiction_ocdid": item.get("jurisdiction_ocdid"),
                        "geoid": item.get("geoid"),
                        "distance_m": item.get("distance_m"),
                    },
                    "geometry": item.get("geojson"),
                }
            )

        return {
            "type": "FeatureCollection",
            "features": features,
            "buffer_m": results.get("buffer_m"),
        }
 
    @router.post("/by-ocdids")
    async def get_jurisdictions_by_ocdids_endpoint(body: JurisdictionsByOcdidsRequest):
        results = await database.get_jurisdictions_by_ocdids(body.ocdids)
        return {"data": results}

    @router.patch("/data")
    async def patch_jurisdiction_data_endpoint(
        request: PatchJurisdictionDataRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.CONTRIBUTORS])),
    ):
        if not user.email:
            return JSONResponse({"error": "User email required"}, status_code=400)
        pull_request_number, pull_request_url_or_error = await jurisdiction_pr_service.open_jurisdiction_edit_pr(
            jurisdiction_ocdid=request.jurisdiction_ocdid,
            fields={"url": request.url, "population": request.population, "geoid": request.geoid},
            author=PrAuthor(name=user.display_name or user.email, email=user.email),
        )
        if pull_request_number is None:
            return JSONResponse({"error": pull_request_url_or_error}, status_code=500)
        return {"data": {"pull_request_number": pull_request_number, "pull_request_url": pull_request_url_or_error}}

    @router.get("/{state}/search")
    async def get_jurisdictions_search_endpoint(
        state: str,
        search_string: str = "",
        limit: int = 0,
        page: int = 1,
    ):
        skip = (page - 1) * limit

        total_items, jurisdictions = await database.search_jurisdictions(
            state, search_string, limit, skip
        )

        next_skip = skip + len(jurisdictions)
        next_link = ""
        prev_link = ""

        if page > 1:
            query_params = urllib.parse.urlencode({"limit": limit, "page": page - 1})
            prev_link = f"/api/v1/jurisdictions/{state}/search?{query_params}"

        if next_skip < total_items:
            query_params = urllib.parse.urlencode({"limit": limit, "page": page + 1})
            next_link = f"/api/v1/jurisdictions/{state}/search?{query_params}"

        self_query_params = urllib.parse.urlencode({"limit": limit, "page": page})
        self_link = f"/api/v1/jurisdictions/{state}/search?{self_query_params}"

        return {
            "total_items": total_items,
            "page": page,
            "total_pages": (total_items + limit - 1) // limit if limit > 0 else 1,
            "limit": limit,
            "data": jurisdictions,
            "links": {"prev": prev_link, "next": next_link, "self": self_link},  # TODO!
        }
    
    @router.get("/history")
    async def get_jurisdiction_history_endpoint(
        jurisdiction_ocdid: str = Query(..., description="The OCD ID of the jurisdiction")
    ):
        database_history = await database.get_jurisdiction_history(jurisdiction_ocdid)

        # Query github for matching pull requests and add to top of history
        # TBD: does this need a cache?
        #pull_request_history = github_service.get_pull_request_history(jurisdiction_ocdid)
        #history = database_history + pull_request_history
        history = database_history

        if history is None:
            raise HTTPException(status_code=404, detail="Jurisdiction not found")

        return {"data": history}

    return router
