from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runners.pipeline03_people_collector.constants import MINIMUM_NUM_PEOPLE
from runners.pipeline03_people_collector.schemas import ExpectedMembership, ResearchMunicipalityStep
from runners.pipeline03_people_collector.transitions.main import research_municipality_transition
from tests.factories.pipeline_run_context import pipeline_run_context_factory

pytestmark = pytest.mark.unit

MODULE = "runners.pipeline03_people_collector.transitions.main"


def _research(expected: int) -> ResearchMunicipalityStep:
    memberships = [
        ExpectedMembership(organization_id="council", role_id=f"seat-{n}", role_label="Council Member")
        for n in range(expected)
    ]
    return ResearchMunicipalityStep(expected_memberships=memberships)


async def _required_after_research(expected: int) -> int:
    context = pipeline_run_context_factory(steps={})
    with patch(f"{MODULE}.research_municipality", new=AsyncMock(return_value=_research(expected))):
        next_context, _ = await research_municipality_transition(MagicMock(), MagicMock(), context, AsyncMock())
    return next_context.data.process_page_content_step.progress.required_data


@pytest.mark.asyncio
async def test_research_sets_the_crawl_target_to_the_memberships_it_expects():
    """The process step starts empty with no target; the crawl's stop rules read the one set here."""
    assert await _required_after_research(MINIMUM_NUM_PEOPLE + 2) == MINIMUM_NUM_PEOPLE + 2


@pytest.mark.asyncio
async def test_a_small_expected_roster_still_targets_the_minimum():
    assert await _required_after_research(1) == MINIMUM_NUM_PEOPLE
