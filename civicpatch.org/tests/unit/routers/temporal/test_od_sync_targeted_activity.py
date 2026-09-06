import pytest
from unittest.mock import AsyncMock, patch
from temporalio.testing import ActivityEnvironment

from routers.temporal.jurisdiction_activities import od_sync_targeted_activity


@pytest.mark.asyncio
@pytest.mark.unit
async def test_targeted_activity_syncs_by_ocdids():
    with patch(
        "routers.temporal.jurisdiction_activities.data_sync.sync_by_ocdids",
        new_callable=AsyncMock,
    ) as mock_sync:
        await ActivityEnvironment().run(od_sync_targeted_activity, ["ocd-a", "ocd-b"])

    mock_sync.assert_awaited_once_with(["ocd-a", "ocd-b"])
