from unittest.mock import AsyncMock, patch

import pytest

from services.review_proposal import review_summary_for_request


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_request_with_no_run_yields_an_empty_summary():
    """Without the guard the jurisdiction lookup dereferences None and the card 500s — a
    request can exist with no pipeline run behind it."""
    with patch(
        "services.review_proposal.get_pipeline_run_result",
        new_callable=AsyncMock,
        return_value=None,
    ):
        assert await review_summary_for_request("missing") == {}
