import urllib.parse

from fastapi import APIRouter, HTTPException, Query


import database.jurisdictions as database

import core.candidate as candidate_service
import shared.utils.config_utils as config_utils
from schemas.requests import JurisdictionsByOcdidsRequest

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
