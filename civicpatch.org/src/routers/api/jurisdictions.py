import urllib.parse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import services.jurisdiction_pull_request as jurisdiction_pr_service
import services.jurisdiction_scrape_candidate as candidate_service
import services.pipeline_issue_resolution as pipeline_issue_resolution_service
import services.role_config as role_config_service
import database.jurisdictions as database
import shared.utils.config_utils as config_utils
from lib.auth import require_route_access
from lib.github.pull_requests import PrAuthor
from schemas.common import Identity, Role, RouteCategory
from schemas.jurisdictions import (
    DeleteRoleRequest,
    ExcludeRoleRequest,
    IncludeExclusionRequest,
    JurisdictionsByOcdidsRequest,
    ReorderGlobalRolesRequest,
    ReorderScopeRolesRequest,
    SetGlobalRolesRequest,
    SetScopeRolesRequest,
)


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
        background_tasks: BackgroundTasks,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)),
    ):
        if not user.email:
            return JSONResponse({"error": "User email required"}, status_code=400)
        pull_request_number, pull_request_url_or_error = await jurisdiction_pr_service.open_jurisdiction_url_pr(
            jurisdiction_ocdid=request.jurisdiction_ocdid,
            url=request.url,
            author=PrAuthor(name=user.display_name or user.email, email=user.email, teams=[user.role] if user.role else []),
            user_id=user.user_id,
        )
        if pull_request_number is None:
            return JSONResponse({"error": pull_request_url_or_error}, status_code=500)
        background_tasks.add_task(
            jurisdiction_pr_service.merge_jurisdiction_pr, str(pull_request_number), user.email
        )
        return {"data": {"pull_request_number": pull_request_number, "pull_request_url": pull_request_url_or_error}}

    @router.get("/config/global")
    async def get_global_config_endpoint(
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)),
    ):
        config = await role_config_service.load_global_config()
        roles = [
            {"role": r.role, "is_unique": r.is_unique, "aliases": r.aliases, "kind": r.kind}
            for r in config.roles
        ]
        return {"data": {"roles": roles}}

    @router.put("/config/global")
    async def put_global_config_endpoint(
        body: SetGlobalRolesRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        try:
            await role_config_service.set_global_roles(body.roles, user_id=user.user_id)
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=409)
        return {"data": {"ok": True}}

    @router.get("/config")
    async def get_jurisdiction_config_endpoint(
        ocdid: str = Query(..., description="The OCD ID of the jurisdiction"),
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)),
    ):
        try:
            per_level = await role_config_service.load_role_config_per_level(ocdid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid jurisdiction OCD ID")
        return {"data": role_config_service.build_merged_response(per_level).model_dump()}

    @router.put("/config")
    async def put_jurisdiction_config_endpoint(
        body: SetScopeRolesRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)),
    ):
        try:
            if body.issue_id:
                await pipeline_issue_resolution_service.resolve_via_config_db(body, user_id=user.user_id, issue_id=body.issue_id)
                return {"data": {"ok": True}}
            await role_config_service.set_scope_roles(body, user_id=user.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid jurisdiction OCD ID")
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=409)
        return {"data": {"ok": True}}

    @router.put("/config/global/reorder")
    async def reorder_global_config_endpoint(
        body: ReorderGlobalRolesRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.ADMINS)),
    ):
        try:
            await role_config_service.reorder_roles("global", None, body.role_order, body.moved_roles, user_id=user.user_id)
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=409)
        return {"data": {"ok": True}}

    @router.put("/config/reorder")
    async def reorder_jurisdiction_config_endpoint(
        body: ReorderScopeRolesRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)),
    ):
        try:
            await role_config_service.reorder_roles(body.scope, body.ocdid, body.role_order, body.moved_roles, user_id=user.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid jurisdiction OCD ID")
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=409)
        return {"data": {"ok": True}}

    @router.post("/config/exclude")
    async def exclude_role_endpoint(
        body: ExcludeRoleRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)),
    ):
        try:
            await role_config_service.exclude_role(body.role, body.scope, body.ocdid, user_id=user.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid jurisdiction OCD ID")
        return {"data": {"ok": True}}

    @router.post("/config/include")
    async def include_role_endpoint(
        body: IncludeExclusionRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)),
    ):
        try:
            await role_config_service.include_role(body.value, body.scope, body.ocdid, user_id=user.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid jurisdiction OCD ID")
        return {"data": {"ok": True}}

    @router.post("/config/delete")
    async def delete_role_endpoint(
        body: DeleteRoleRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, Role.MAINTAINERS)),
    ):
        try:
            await role_config_service.delete_role(body.role, body.scope, body.ocdid, user_id=user.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid jurisdiction OCD ID")
        return {"data": {"ok": True}}

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
