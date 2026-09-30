"""A run's frontier as `source_pages` rows: one per page the run tried to fetch."""

from typing import Optional

from pydantic import BaseModel
from shared.utils import id_utils

# The pipeline's `LinkStatus` values (pipelines/src/runners/people_collector/schemas.py)
# this module reads.
LINK_STATUS_PENDING = "pending"
LINK_STATUS_HEURISTICS_FAIL = "processed_heuristics_fail"


class FrontierLink(BaseModel):
    """One link from `pipeline_run_context.json`, the fields a row needs."""

    url: str
    status: str
    folder_name: str = ""
    text: Optional[str] = None
    organization_ids: list[str] = []
    is_relevant: Optional[bool] = None
    relevant_urls: Optional[list[str]] = None
    page_hash: Optional[str] = None
    prompt_hash: Optional[str] = None
    heuristics_failures: list[str] = []
    unchanged_since_source_page_id: Optional[str] = None


class SourcePageRow(BaseModel):
    source_url: str
    jurisdiction_ocdid: str
    pipeline_run_id: str
    changeset_id: Optional[str]
    organization_ids: list[str]
    page_hash: Optional[str]
    prompt_hash: Optional[str]
    cache_path: Optional[str]
    anchor_text: Optional[str]
    is_relevant: Optional[bool]
    relevant_urls: Optional[list[str]]
    heuristics_failures: list[str]
    unchanged_since_source_page_id: Optional[str] = None


def frontier_links(workflow_context: dict) -> list[FrontierLink]:
    """Absent on a run that failed before writing a context, which is no links, not an error."""
    links = workflow_context.get("data", {}).get("frontier", {}).get("links", {})
    return [FrontierLink.model_validate(link) for link in links.values()]


def source_page_rows(
    links: list[FrontierLink],
    pipeline_run_id: str,
    jurisdiction_ocdid: str,
    changeset_id: Optional[str],
) -> list[SourcePageRow]:
    jurisdiction_folder = id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    return [
        SourcePageRow(
            source_url=link.url,
            jurisdiction_ocdid=jurisdiction_ocdid,
            pipeline_run_id=pipeline_run_id,
            changeset_id=changeset_id,
            organization_ids=read_organization_ids(link),
            page_hash=link.page_hash,
            prompt_hash=link.prompt_hash,
            cache_path=_cache_path(pipeline_run_id, jurisdiction_folder, link.folder_name),
            anchor_text=link.text,
            is_relevant=link.is_relevant,
            relevant_urls=link.relevant_urls,
            heuristics_failures=link.heuristics_failures,
            unchanged_since_source_page_id=link.unchanged_since_source_page_id,
        )
        for link in links
        if link.status != LINK_STATUS_PENDING
    ]


def read_organization_ids(link: FrontierLink) -> list[str]:
    """A page whose extraction failed has no records, so counting it as a read of the
    organizations it covers would retire their people."""
    if link.status == LINK_STATUS_HEURISTICS_FAIL:
        return []
    return link.organization_ids


def _cache_path(pipeline_run_id: str, jurisdiction_folder: str, folder_name: str) -> Optional[str]:
    # Mirrors cp.org's upload: `<run id>/` + the path under the zip's debug files.
    if not folder_name:
        return None
    return f"{pipeline_run_id}/data_source/{jurisdiction_folder}/cache/{folder_name}"
