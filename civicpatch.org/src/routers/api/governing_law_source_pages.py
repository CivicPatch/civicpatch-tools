"""A jurisdiction's governing-law source pages, for the collectors and the team: stored
whole, read back by id."""

import services.governing_law_source_pages as source_pages_service
from fastapi import APIRouter, Depends, HTTPException
from lib.auth import require_route_access
from pydantic import BaseModel
from schemas.common import Identity, RouteCategory, ServiceKey


class GoverningLawSourcePageRequest(BaseModel):
    source_url: str
    text: str


def get_router() -> APIRouter:
    router = APIRouter()
    access = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, service_key=ServiceKey.ACCEPTED))

    @router.post("/{jurisdiction_ocdid:path}/governing_law_source_pages", include_in_schema=False)
    async def post_governing_law_source_page_endpoint(
        jurisdiction_ocdid: str, body: GoverningLawSourcePageRequest, _: Identity = access
    ):
        try:
            page = await source_pages_service.store_source_page(jurisdiction_ocdid, body.source_url, body.text)
        except source_pages_service.UnknownJurisdiction:
            raise HTTPException(status_code=404, detail=f"No such jurisdiction: {jurisdiction_ocdid}")
        except source_pages_service.NotPlainText:
            raise HTTPException(status_code=422, detail="The cache takes text, not a page: strip the HTML first.")
        return {"data": page.model_dump(mode="json")}

    @router.get("/{jurisdiction_ocdid:path}/governing_law_source_pages/{source_page_id}", include_in_schema=False)
    async def get_governing_law_source_page_endpoint(jurisdiction_ocdid: str, source_page_id: str, _: Identity = access):
        try:
            found = await source_pages_service.read_source_page(jurisdiction_ocdid, source_page_id)
        except source_pages_service.SourcePageNotFound:
            raise HTTPException(status_code=404, detail=f"No source page {source_page_id} for {jurisdiction_ocdid}")
        return {"data": {**found.page.model_dump(mode="json"), "text": found.text}}

    return router
