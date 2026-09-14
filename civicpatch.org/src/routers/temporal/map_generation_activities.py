"""The activity a map-generation workflow runs: build one state's pmtiles and upload it.

`services/map_generation.py` is the machinery; this is the Temporal-facing seam onto it,
same split as sink_activities.py/source_activities.py.
"""

from temporalio import activity

from services.map_generation import (
    generate_and_upload_national_overview,
    generate_and_upload_state_pmtiles,
)


@activity.defn
async def build_and_upload_state_pmtiles(state: str) -> str:
    """Returns the CDN URL of the uploaded {state}.pmtiles."""
    return await generate_and_upload_state_pmtiles(state)


@activity.defn
async def build_and_upload_national_overview() -> str:
    """Returns the CDN URL of the rebuilt states.pmtiles (the coverage picker)."""
    return await generate_and_upload_national_overview()
