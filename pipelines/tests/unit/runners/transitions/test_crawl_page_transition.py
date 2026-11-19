from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from runners.pipeline03_people_collector.schemas import LinkFrontier
from runners.pipeline03_people_collector.transitions.main import crawl_page_transition
from tests.factories.pipeline_run_context import pipeline_run_context_factory

pytestmark = pytest.mark.unit

MODULE = "runners.pipeline03_people_collector.transitions.main"


@pytest.mark.asyncio
async def test_a_crash_while_crawling_reaches_the_engine():
    """The engine records a raised step as the run's `failure`, which cp.org files as the issue;
    a catch here would hide the state that failed."""
    context = pipeline_run_context_factory(steps={})
    frontier = LinkFrontier.from_urls(["https://example.gov"])
    context = context.model_copy(update={"data": context.data.model_copy(update={"frontier": frontier})})

    with patch(f"{MODULE}.crawl_page", new=AsyncMock(side_effect=ValueError("boom"))):
        with pytest.raises(ValueError, match="boom"):
            await crawl_page_transition(MagicMock(), MagicMock(), context, AsyncMock())
