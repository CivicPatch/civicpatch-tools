"""WRITE: VERIFY's posts onto the jurisdiction, or nothing when no law was read."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runners.organizations_collector.schemas import (
    OrganizationsCollectorConfig,
    OrganizationsCollectorContext,
    OrganizationsCollectorData,
    OrganizationsCollectorStep,
    RoleOutcomes,
)
from runners.organizations_collector.transitions.main import write
from shared.schemas import (
    FoundBy,
    GoverningLaw,
    GoverningLawKind,
    GoverningLawPost,
    QuoteScope,
    Source,
    SourceExtras,
)
from shared.utils.layered_config import ConfigFile, merged_config
from shared.utils.statuses import PipelineRunStatus

pytestmark = pytest.mark.unit

_OCDID = "ocd-jurisdiction/country:us/state:vt/place:stowe/government"
_COLLECTED_AT = datetime(2026, 10, 19, tzinfo=timezone.utc)
_LAW = GoverningLaw(
    kind=GoverningLawKind.CHARTER, classification="town", found_by=FoundBy.STATE_INDEX,
    source_page_ids=["charter"], collected_at=_COLLECTED_AT, cost_usd=None,
)
_MEMBER = GoverningLawPost(
    role="member", label="Selectboard member", organization_id="Select Board", maximum_memberships=5,
    sources=[Source(url="https://example.gov/charter", note="five members elected at large", extras=SourceExtras(source_page_id="charter", matched_in=QuoteScope.SENTENCE))],
)


def _context(governing_law: GoverningLaw | None, outcomes: RoleOutcomes | None) -> OrganizationsCollectorContext:
    return OrganizationsCollectorContext(
        pipeline_run_id="run-1",
        current_state=OrganizationsCollectorStep.WRITE,
        data=OrganizationsCollectorData(
            jurisdiction_ocdid=_OCDID,
            config=OrganizationsCollectorConfig(
                name="Stowe town", governing_law=governing_law,
                jurisdiction_config=merged_config(ConfigFile(), ConfigFile(), ConfigFile()), government_form=None,
            ),
            outcomes=outcomes,
        ),
    )


async def _write(context: OrganizationsCollectorContext):
    patch_extras = AsyncMock()
    with patch("runners.organizations_collector.transitions.main.civicpatch_api.patch_jurisdiction_extras", new=patch_extras):
        written, state = await write(MagicMock(), MagicMock(), context, MagicMock())
    return written, state, patch_extras


@pytest.mark.asyncio
async def test_the_posts_are_written_with_the_law_they_were_read_from():
    written, state, patch_extras = await _write(_context(_LAW, RoleOutcomes(posts=[_MEMBER])))

    assert state == PipelineRunStatus.SUCCESS
    [call] = patch_extras.await_args_list
    _client, ocdid, extras = call.args
    assert ocdid == _OCDID
    assert extras.extras_organizations.posts == [_MEMBER]
    assert extras.extras_organizations.extras.governing_law_collected_at == _COLLECTED_AT
    assert written.data.organizations == extras.extras_organizations


@pytest.mark.asyncio
async def test_a_law_that_establishes_nothing_is_written_as_no_posts():
    _, _, patch_extras = await _write(_context(_LAW, RoleOutcomes()))

    [call] = patch_extras.await_args_list
    assert call.args[2].extras_organizations.posts == []


@pytest.mark.asyncio
async def test_no_law_read_writes_nothing():
    _, state, patch_extras = await _write(_context(None, None))

    assert state == PipelineRunStatus.SUCCESS
    patch_extras.assert_not_awaited()
