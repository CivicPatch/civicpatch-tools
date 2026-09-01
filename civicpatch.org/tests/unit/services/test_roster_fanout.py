"""The bulk review reads one roster per request, and the pool is finite.

A forty-locality import used to fan out unbounded here: each roster holds two pool connections
at its widest against a pool of twenty, so every one of them waited out the 30s timeout and the
page 500'd. What matters is the ceiling, not the speed.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from services import roster


@pytest.mark.unit
@pytest.mark.asyncio
async def test_roster_reads_are_capped_however_many_requests():
    """Forty requests must not become forty concurrent connection holders."""
    ocdids = {f"request-{n}": f"ocd-{n}" for n in range(40)}
    live = 0
    peak = 0

    async def slow_roster(request_id: str, ocdid: str) -> list[dict]:
        nonlocal live, peak
        live += 1
        peak = max(peak, live)
        # Long enough that every caller overlaps if nothing is holding them back.
        await asyncio.sleep(0.01)
        live -= 1
        return [{"id": request_id}]

    with (
        patch(
            "services.roster.changesets_db.jurisdictions_for_requests",
            new_callable=AsyncMock,
            return_value=ocdids,
        ),
        patch("services.roster.proposed_roster", side_effect=slow_roster),
    ):
        rosters = await roster.proposed_rosters(list(ocdids))

    assert peak <= roster._ROSTER_CONCURRENCY
    # Capping must not drop anybody.
    assert len(rosters) == 40


@pytest.mark.unit
@pytest.mark.asyncio
async def test_no_requests_reads_nothing():
    with patch(
        "services.roster.changesets_db.jurisdictions_for_requests",
        new_callable=AsyncMock,
    ) as lookup:
        assert await roster.proposed_rosters([]) == {}
    lookup.assert_not_awaited()
