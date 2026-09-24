from unittest.mock import AsyncMock, patch

import pytest

from core.review_summary import ReviewSummary
from services.review_summary import review_summary_for_changeset


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_request_we_do_not_hold_yields_an_empty_summary():
    """The summary is computed from the jurisdiction's rosters now, so an unknown request has
    nothing to compute against — and must not 500 the card looking."""
    with patch(
        "services.review_summary.changesets_db.get_changeset_jurisdiction",
        new_callable=AsyncMock,
        return_value=None,
    ):
        assert await review_summary_for_changeset("missing") == ReviewSummary()
