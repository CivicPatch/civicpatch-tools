import os
import urllib

import yaml
from fastapi import APIRouter, HTTPException, Query

import database
import services.github_service as github_service
# import services.auth_service as AuthService
from schemas.common import Jurisdiction

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


def get_router() -> APIRouter:
    router = APIRouter()

    @router.get("")
    async def get_jurisdiction_data_endpoint(
        jurisdiction_ocdid: str = Query(..., description="The OCD ID of the jurisdiction"),
        with_geom: bool = False,
    ):
        jurisdiction_data = await database.get_jurisdiction(jurisdiction_ocdid, with_geom)

        if jurisdiction_data is None:
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
        jurisdictions_file_content = await github_service.get_github_file_contents(
            f"data_source/{state}/jurisdictions.yml"
        )
        jurisdictions_metadata_file_content = await github_service.get_github_file_contents(
            f"data_source/{state}/jurisdictions_metadata.yml"
        )
        if jurisdictions_metadata_file_content is None:
            raise HTTPException(
                status_code=404, detail="Could not find jurisdictions metadata file"
            )

        if jurisdictions_file_content is None:
            raise HTTPException(
                status_code=404, detail="Could not find jurisdictions file"
            )
        # Combine metadata with jurisdiction entries from jurisdiction.yml, 
        # filtering out jurisdictions with open pull requests or recently updated metadata
        jurisdictions_metadata = yaml.safe_load(jurisdictions_metadata_file_content)
        jurisdictions_data = yaml.safe_load(jurisdictions_file_content)
        jurisdictions = []
        open_pull_requests = await github_service.get_open_pull_requests()
        jurisdictions_entries = jurisdictions_data.get("jurisdictions", [])
        for jurisdiction_ocdid, jurisdiction_metadata in jurisdictions_metadata.get("jurisdictions_by_id", {}).items():
            print("grabbing metadata for", jurisdiction_ocdid)
            # Skip over if updated_at is populated (TODO: new condition needed)
            if jurisdiction_metadata.get("updated_at"):
                continue
            # Skip over if there's an open pull request for this jurisdiction
            if any(pr.jurisdiction_ocdid == jurisdiction_ocdid for pr in open_pull_requests):
                continue
            # Need to find matching jurisdiction_entry under "jurisdictions" array field
            jurisdiction_entry = next((entry for entry in jurisdictions_entries if entry.get("id") == jurisdiction_ocdid), None)

            # Skip over if no url 
            if not jurisdiction_entry.get("url"):
                continue

            if jurisdiction_entry:
                jurisdiction_metadata["jurisdiction"] = jurisdiction_entry
                jurisdictions.append(
                    Jurisdiction(
                        id=jurisdiction_metadata["jurisdiction"]["id"],
                        name=jurisdiction_metadata["jurisdiction"]["name"],
                        url=jurisdiction_metadata["jurisdiction"]["url"],
                    )
                )

        filtered_jurisdictions = jurisdictions[:num_jurisdictions]
        return {"jurisdictions": filtered_jurisdictions}

    @router.get("/states")
    async def get_jurisdiction_states_endpoint(
    ):
        states = await database.get_jurisdiction_states()

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
