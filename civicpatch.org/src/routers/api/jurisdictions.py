import urllib.parse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

import services.jurisdiction_pull_request as jurisdiction_pr_service
import services.jurisdiction_scrape_candidate as candidate_service
import database.changesets as changesets
import database.jurisdictions as database
import lib.cache as cache_service
from lib.auth import require_route_access
from schemas.common import Identity, UserRole, RouteCategory
from core.jurisdiction_search import build_fuzzy_tokens, build_tsquery
from schemas.jurisdictions import (
    JurisdictionSearchResult,
    JurisdictionSearchResponse,
    JurisdictionsByOcdidsRequest,
    PaginationLinks,
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
    # url_utils.format_url would silently prepend a scheme to a typo.
    #
    # An emptied input arrives as "" and is normalised to None — the user clearing the box is
    # the same decision as sending null, and null is what the patch writes. The field still
    # counts as set, so exclude_unset keeps it and the value is cleared rather than skipped.
    @field_validator("url")
    @classmethod
    def validate_url(cls, v):
        if v is None or not v.strip():
            return None
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
        # exclude_unset, not a dict literal: a field the caller omitted must stay omitted, or
        # its None becomes indistinguishable from an explicit null and every edit would clear
        # the two fields it did not mention.
        commit_url, url_or_error, _changeset_id = await jurisdiction_pr_service.commit_jurisdiction_patch(
            jurisdiction_ocdid=request.jurisdiction_ocdid,
            fields=request.model_dump(exclude_unset=True),
            user_id=user.user_id,
        )
        if commit_url is None:
            # Nothing to write is the caller's mistake, not a server failure.
            no_op = url_or_error in set(jurisdiction_pr_service.EditRejection)
            return JSONResponse({"error": url_or_error}, status_code=400 if no_op else 500)
        # No background merge: the commit already landed, so the response is the outcome.
        return {"data": {"change_url": commit_url}}

    @router.get("/search")
    async def search_jurisdictions_endpoint(
        q: str = "",
        state: str = "",
        level: str = "",
        limit: int = Query(DEFAULT_SEARCH_LIMIT, ge=1, le=MAX_SEARCH_LIMIT),
        page: int = Query(1, ge=1),
    ) -> JurisdictionSearchResponse:
        # `level` limits the jurisdiction level(s), e.g. "local" or "local,counties".
        # Defaults to both local and counties when empty.
        levels = [l.strip() for l in level.split(",") if l.strip()] if level else SEARCHABLE_LEVELS

        # A `state` filter scopes the search to a single state (used by the
        # config editor's locality picker). Without it, searches nationwide.
        if state:
            total_items, jurisdictions = await database.search_jurisdictions(
                state, q, limit, (page - 1) * limit
            )
            results = [
                JurisdictionSearchResult(
                    jurisdiction_ocdid=j["jurisdiction_ocdid"],
                    level="local",
                    name=j.get("name", ""),
                    display_name=j.get("display_name"),
                    population=j.get("population"),
                    url=j.get("url"),
                    parent_names=j.get("parent_ocdids", []),
                )
                for j in jurisdictions
            ]
            return JurisdictionSearchResponse(
                total_items=total_items,
                page=page,
                total_pages=(total_items + limit - 1) // limit if limit > 0 else 1,
                limit=limit,
                data=results,
                links=PaginationLinks.model_validate({
                    "prev": f"/api/v1/jurisdictions/search?{urllib.parse.urlencode({'q': q, 'state': state, 'limit': limit, 'page': page - 1})}" if page > 1 else "",
                    "next": f"/api/v1/jurisdictions/search?{urllib.parse.urlencode({'q': q, 'state': state, 'limit': limit, 'page': page + 1})}" if (page * limit) < total_items else "",
                    "self": f"/api/v1/jurisdictions/search?{urllib.parse.urlencode({'q': q, 'state': state, 'limit': limit, 'page': page})}",
                })
            )

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
            tsquery, levels, limit, skip
        )
        if total_items == 0:
            total_items, results = await database.search_jurisdictions_fuzzy(
                build_fuzzy_tokens(q), levels, limit, skip
            )
        response = JurisdictionSearchResponse(
            total_items=total_items,
            page=page,
            total_pages=(total_items + limit - 1) // limit,
            limit=limit,
            data=results,
            links=_search_links(normalized, limit, page, skip + len(results), total_items),
        )
        await cache_service.set_cached(
            cache_key,
            response.model_dump(mode="json", by_alias=True),
            SEARCH_CACHE_TTL_SECONDS,
        )
        return response

    # The house pagination shape: `page` + `per_page` in, `{total_items, page, total_pages,
    # data}` out — 9 of 12 paged endpoints take these params and 5 return this envelope.
    # `offset` stays inside the database layer, where the window is what the query wants.
    @router.get("/history")
    async def get_jurisdiction_history_endpoint(
        jurisdiction_ocdid: str = Query(..., description="The OCD ID of the jurisdiction"),
        page: int = Query(1, ge=1),
        per_page: int = Query(database.DEFAULT_HISTORY_LIMIT, ge=1, le=100),
    ):
        total, history = await database.get_jurisdiction_history(
            jurisdiction_ocdid, limit=per_page, offset=(page - 1) * per_page
        )
        return {
            "total_items": total,
            "page": page,
            "total_pages": max(1, (total + per_page - 1) // per_page),
            "data": history,
        }

    # Public, like the history it summarises: the jurisdiction page is public and each action
    # gates itself. This is the whole-history fetch that page used to do, narrowed to the rows
    # it actually derives from.
    @router.get("/in-flight")
    async def get_jurisdiction_in_flight_endpoint(
        jurisdiction_ocdid: str = Query(..., description="The OCD ID of the jurisdiction")
    ):
        return {"data": await changesets.get_in_flight(jurisdiction_ocdid)}

    return router
