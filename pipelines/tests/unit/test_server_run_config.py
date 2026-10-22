"""The local server builds a people run's config from cp.org's answer field by field, so a field
cp.org adds reaches the run only if it is copied here too (`governing_law_posts` was not, 2026-10-22)."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

import server

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:vt/place:charlotte/government"
_LAW_POST = {
    "role": "moderator",
    "label": "Moderator",
    "organization_id": "Town Meeting",
    "maximum_memberships": 1,
    "sources": [{"url": "https://x.gov", "note": "a moderator", "extras": {"source_page_id": "p", "matched_in": "sentence"}}],
    "extras": {"selection_method": "elected_by_voters"},
}


@pytest.mark.asyncio
async def test_a_people_run_is_handed_the_governing_law_posts_cp_org_sends():
    started = AsyncMock()
    tasks: list[asyncio.Task] = []
    config_data = {"url": "https://charlottevt.org", "name": "Charlotte town", "governing_law_posts": [_LAW_POST]}

    with (
        patch("server.get_env_vars", return_value={"SERVICE_API_KEY": "key"}),
        patch("server.civicpatch_api.fetch_pipeline_run_config", new=AsyncMock(return_value=config_data)),
        patch("server.start_threaded", new=started),
        patch("server._track", side_effect=lambda _id, task: tasks.append(task)),
    ):
        await server._run("run-1", _OCDID, None, None)
        await asyncio.gather(*tasks)

    config = started.call_args.args[2]
    assert [(post.organization_id, post.role, post.maximum_memberships) for post in config.governing_law_posts] == [
        ("Town Meeting", "moderator", 1)
    ]
