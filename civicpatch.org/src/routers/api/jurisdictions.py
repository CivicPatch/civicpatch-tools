import urllib.parse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

import services.jurisdiction_pull_request as jurisdiction_pr_service
import services.jurisdiction_scrape_candidate as candidate_service
import services.pipeline_issue_resolution as pipeline_issue_resolution_service
import services.role_config as role_config_service
import database.jurisdictions as database
import lib.cache as cache_service
from lib.auth import require_route_access
from lib.github.pull_requests import PrAuthor
from schemas.common import Identity, UserRole, RouteCategory
from core.jurisdiction_search import build_fuzzy_tokens, build_tsquery
from schemas.jurisdictions import (
    DeleteRoleRequest,
    JurisdictionSearchResponse,
    JurisdictionsByOcdidsRequest,
    PaginationLinks,
    ReorderGlobalRolesRequest,
    ReorderScopeRolesRequest,
    SetGlobalRolesRequest,
    SetScopeRolesRequest,
)
from shared.schemas import JurisdictionLevel

# Typeahead returns a short list plus the true match count; refinement narrows it rather
# than paging. MAX caps what a caller can ask for.
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 50

# State rows exist to supply state names to search_text; they are never results.
# Annotated list[str] because list is invariant — list[JurisdictionLevel] is not a
# list[str], even though every JurisdictionLevel is one.
SEARCHABLE_LEVELS: list[str] = [JurisdictionLevel.LOCAL, JurisdictionLevel.COUNTIES]

SEARCH_PATH = "/api/v1/jurisdictions/search"

# Jurisdictions change only on sync, so a short TTL is enough and no invalidation is
# wired up: a query-keyed cache has unbounded cardinality and no single key to drop.
# Accepted cost is up to this many seconds of staleness after a sync.
SEARCH_CACHE_TTL_SECONDS = 60


def _normalized_query(query: str) -> str:
    # Same tokenizer the search itself uses, so "Seattle, WA" and "seattle  wa" share a
    # cache entry. Used for the links too — keying on one spelling while embedding
    # another would serve a hit whose next/prev pointed at a different search.
    return " ".join(build_fuzzy_tokens(query))


def _search_cache_key(query: str, limit: int, page: int) -> str:
    return f"jurisdiction_search:{query}:{limit}:{page}"


def _search_link(query: str, limit: int, page: int) -> str:
    # q is carried through: a next/prev link without it would page a different search.
    params = urllib.parse.urlencode({"q": query, "limit": limit, "page": page})
    return f"{SEARCH_PATH}?{params}"


def _search_links(
    query: str, limit: int, page: int, next_skip: int, total_items: int
) -> PaginationLinks:
    return PaginationLinks(
        prev=_search_link(query, limit, page - 1) if page > 1 else "",
        next=_search_link(query, limit, page + 1) if next_skip < total_items else "",
        **{"self": _search_link(query, limit, page)},
    )


def _empty_search_response(
    query: str, limit: int, page: int
) -> JurisdictionSearchResponse:
    return JurisdictionSearchResponse(
        total_items=0,
        page=page,
        total_pages=0,
        limit=limit,
        data=[],
        links=_search_links(query, limit, page, 0, 0),
    )


class PatchJurisdictionDataRequest(BaseModel):
    jurisdiction_ocdid: str
    url: str | None = None
    geoid: str | None = None
    population: int | None = None

    # Mirrors urlError in field-validation.ts, so the reviewer is told the same thing
    # while typing as they would be on Save. Rejects rather than canonicalizing:
    # url_utils.format_url would silently prepend a scheme to a typo. Clearing the
    # website is allowed, so only a non-empty value is judged.
    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        if v is None or not v.strip():
            return v
        url = v.strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"Website must start with 'http://' or 'https://', got: '{url}'")
        parsed = urllib.parse.urlparse(url)
        if not parsed.netloc or "." not in parsed.netloc or " " in url:
            raise ValueError(f"Website must be a valid URL with a domain, got: '{url}'")
        return url

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
            "scraped_at": jurisdiction_data.get("scraped_at"),
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
    async def get_jurisdiction_states_endpoint():
        states = await database.get_states_with_names()

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
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ):
        if not user.email:
            return JSONResponse({"error": "User email required"}, status_code=400)
        pull_request_number, pull_request_url_or_error, request_id = await jurisdiction_pr_service.open_jurisdiction_patch_pr(
            jurisdiction_ocdid=request.jurisdiction_ocdid,
            fields={"url": request.url, "geoid": request.geoid, "population": request.population},
            author=PrAuthor(name=user.display_name or user.email, email=user.email, teams=[user.role] if user.role else []),
            user_id=user.user_id,
        )
        if pull_request_number is None:
            # Nothing to write is the caller's mistake, not a server failure.
            no_op = pull_request_url_or_error in set(jurisdiction_pr_service.EditRejection)
            return JSONResponse(
                {"error": pull_request_url_or_error}, status_code=400 if no_op else 500
            )
        background_tasks.add_task(
            jurisdiction_pr_service.merge_jurisdiction_pr,
            str(pull_request_number),
            user.email,
            request_id,
        )
        return {"data": {"pull_request_number": pull_request_number, "pull_request_url": pull_request_url_or_error}}

    @router.get("/config/global")
    async def get_global_config_endpoint(
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ):
        config = await role_config_service.load_global_config()
        roles = [
            {
                "role": r.label,
                "label": r.label,
                "status": r.status,
                "is_unique": r.is_unique,
                "priority": r.priority,
                "aliases": r.aliases,
            }
            for r in config.roles
        ]
        return {"data": {"roles": roles}}

    @router.put("/config/global")
    async def put_global_config_endpoint(
        body: SetGlobalRolesRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)),
    ):
        try:
            await role_config_service.set_global_roles(body.roles, user_id=user.user_id)
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=409)
        return {"data": {"ok": True}}

    @router.get("/config")
    async def get_jurisdiction_config_endpoint(
        ocdid: str = Query(..., description="The OCD ID of the jurisdiction"),
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ):
        try:
            per_level = await role_config_service.load_role_config_per_level(ocdid)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid jurisdiction OCD ID")
        return {"data": role_config_service.build_merged_response(per_level).model_dump()}

    @router.put("/config")
    async def put_jurisdiction_config_endpoint(
        body: SetScopeRolesRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
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
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)),
    ):
        try:
            await role_config_service.reorder_roles("global", None, body.role_order, body.moved_roles, user_id=user.user_id)
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=409)
        return {"data": {"ok": True}}

    @router.put("/config/reorder")
    async def reorder_jurisdiction_config_endpoint(
        body: ReorderScopeRolesRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ):
        try:
            await role_config_service.reorder_roles(body.scope, body.ocdid, body.role_order, body.moved_roles, user_id=user.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid jurisdiction OCD ID")
        except RuntimeError as e:
            return JSONResponse({"error": str(e)}, status_code=409)
        return {"data": {"ok": True}}


    @router.post("/config/delete")
    async def delete_role_endpoint(
        body: DeleteRoleRequest,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ):
        try:
            await role_config_service.delete_role(body.role, body.scope, body.ocdid, user_id=user.user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid jurisdiction OCD ID")
        return {"data": {"ok": True}}

    @router.get("/search")
    async def search_jurisdictions_endpoint(
        q: str = "",
        limit: int = Query(DEFAULT_SEARCH_LIMIT, ge=1, le=MAX_SEARCH_LIMIT),
        page: int = Query(1, ge=1),
    ) -> JurisdictionSearchResponse:
        # Nationwide, unlike /{state}/search. The typeahead only ever asks for page 1 and
        # renders "top 10 of 121", but the results are a real paged collection so other
        # /api/v1 consumers can walk the whole set.
        normalized = _normalized_query(q)
        tsquery = build_tsquery(q)
        if not tsquery:
            return _empty_search_response(normalized, limit, page)

        cache_key = _search_cache_key(normalized, limit, page)
        cached = await cache_service.get_cached(cache_key)
        if cached:
            return JurisdictionSearchResponse(**cached)

        skip = (page - 1) * limit
        total_items, results = await database.search_jurisdictions_by_text(
            tsquery, SEARCHABLE_LEVELS, limit, skip
        )
        # Tier 2 only when tier 1 found nothing at all, never merged in. The tiers are
        # scored differently, so mixing them would make ranking incoherent — and because
        # the switch keys off the total rather than this page, every page of a given
        # query is served by the same tier.
        if total_items == 0:
            total_items, results = await database.search_jurisdictions_fuzzy(
                build_fuzzy_tokens(q), SEARCHABLE_LEVELS, limit, skip
            )
        response = JurisdictionSearchResponse(
            total_items=total_items,
            page=page,
            total_pages=(total_items + limit - 1) // limit,
            limit=limit,
            data=results,
            links=_search_links(
                normalized, limit, page, skip + len(results), total_items
            ),
        )
        # by_alias so the cached dict round-trips: PaginationLinks stores the field as
        # self_link but is populated by its "self" alias.
        await cache_service.set_cached(
            cache_key,
            response.model_dump(mode="json", by_alias=True),
            SEARCH_CACHE_TTL_SECONDS,
        )
        return response

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
