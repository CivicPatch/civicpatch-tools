from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.request_utils import with_retry

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_a_named_error_is_raised_without_a_retry():
    call = AsyncMock(side_effect=KeyError("no answer"))

    with pytest.raises(KeyError):
        await with_retry(MagicMock(), call, not_retried=(KeyError,))

    assert call.await_count == 1


@pytest.mark.asyncio
async def test_any_other_error_is_still_retried(monkeypatch):
    monkeypatch.setattr("utils.request_utils.asyncio.sleep", AsyncMock())
    call = AsyncMock(side_effect=[ConnectionError("502"), "answer"])

    assert await with_retry(MagicMock(), call, not_retried=(KeyError,)) == "answer"
