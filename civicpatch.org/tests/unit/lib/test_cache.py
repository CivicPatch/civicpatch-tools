import json

import pytest
from unittest.mock import AsyncMock, patch

import lib.cache as cache_service


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None):
        self.store[key] = value
        self.ttls[key] = ttl

    async def delete(self, key: str):
        self.store.pop(key, None)
        self.ttls.pop(key, None)


@pytest.fixture
def fake_redis():
    fake = FakeRedis()
    with (
        patch("lib.redis.get", side_effect=fake.get),
        patch("lib.redis.set", side_effect=fake.set),
        patch("lib.redis.delete", side_effect=fake.delete),
    ):
        yield fake


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_then_get_round_trips_dict(fake_redis):
    await cache_service.set_cached("k", {"name": "alice", "count": 5})
    result = await cache_service.get_cached("k")
    assert result == {"name": "alice", "count": 5}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_then_get_round_trips_empty_dict_as_falsy(fake_redis):
    """Regression: empty dict was being cached as {expires_at: ...} which is truthy,
    causing the router to return empty data forever instead of re-fetching."""
    await cache_service.set_cached("k", {})
    result = await cache_service.get_cached("k")
    assert result == {} or result is None
    assert not result, "empty cached value must be falsy so callers treat it as miss/empty"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_on_missing_key_returns_none(fake_redis):
    result = await cache_service.get_cached("never-set")
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_invalidate_removes_key(fake_redis):
    await cache_service.set_cached("k", {"v": 1})
    await cache_service.invalidate("k")
    result = await cache_service.get_cached("k")
    assert result is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_with_ttl_passes_ttl_to_redis(fake_redis):
    await cache_service.set_cached("k", {"v": 1}, ttl_seconds=120)
    assert fake_redis.ttls["k"] == 120


@pytest.mark.unit
@pytest.mark.asyncio
async def test_set_default_ttl_is_one_hour(fake_redis):
    await cache_service.set_cached("k", {"v": 1})
    assert fake_redis.ttls["k"] == 3600
