import json
from datetime import datetime, timezone

import pytest

from services import blog_sync
from services.blog_sync import (
    INDEX_KEY,
    POST_KEY_PREFIX,
    SyncCollisionError,
    sync_blog_posts,
)
from schemas.webhooks.blog_sync import BlogSyncPayload, DiscussionPayload


def _make_discussion(
    number: int = 42,
    title: str = "Test Post",
    body: str = "---\nslug: test\ndescription: hi\n---\nHello",
    labels: list[str] | None = None,
    author_login: str = "testuser",
    created_at: datetime | None = None,
) -> DiscussionPayload:
    return DiscussionPayload(
        number=number,
        title=title,
        body=body,
        created_at=created_at or datetime(2026, 5, 14, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 14, tzinfo=timezone.utc),
        author_login=author_login,
        labels=labels or [],
        url=f"https://github.com/x/y/discussions/{number}",
    )


@pytest.fixture
def mock_redis(mocker):
    async def fake_existing() -> set[str]:
        return set()

    mocker.patch.object(blog_sync, "_existing_post_slugs", side_effect=fake_existing)
    set_mock = mocker.patch.object(blog_sync.redis_store, "set", new=mocker.AsyncMock())
    delete_mock = mocker.patch.object(blog_sync.redis_store, "delete", new=mocker.AsyncMock())
    return set_mock, delete_mock


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_happy_path_writes_per_post_and_index(mock_redis):
    set_mock, _ = mock_redis
    d = _make_discussion(body="---\nslug: hello\n---\nBody.")
    payload = BlogSyncPayload(discussions=[d])

    result = await sync_blog_posts(payload)

    assert result.synced == ["hello"]
    assert result.skipped == []

    set_keys = [call.args[0] for call in set_mock.call_args_list]
    assert f"{POST_KEY_PREFIX}hello" in set_keys
    assert INDEX_KEY in set_keys


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_skips_drafts_silently(mock_redis):
    set_mock, _ = mock_redis
    draft = _make_discussion(number=1, labels=["draft"], body="---\nslug: drafted\n---\nx")
    payload = BlogSyncPayload(discussions=[draft])

    result = await sync_blog_posts(payload)

    assert result.synced == []
    assert result.skipped == []
    set_keys = [call.args[0] for call in set_mock.call_args_list]
    assert not any(k.startswith(POST_KEY_PREFIX) for k in set_keys)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_skips_post_without_frontmatter(mock_redis):
    set_mock, _ = mock_redis
    bad = _make_discussion(number=7, body="no frontmatter here")
    good = _make_discussion(number=8, body="---\nslug: ok\n---\nBody")
    payload = BlogSyncPayload(discussions=[bad, good])

    result = await sync_blog_posts(payload)

    assert result.synced == ["ok"]
    assert result.skipped == [(7, "no frontmatter")]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_raises_collision_and_writes_nothing(mock_redis):
    set_mock, _ = mock_redis
    d1 = _make_discussion(number=1, body="---\nslug: same\n---\nA")
    d2 = _make_discussion(number=2, body="---\nslug: same\n---\nB")
    payload = BlogSyncPayload(discussions=[d1, d2])

    with pytest.raises(SyncCollisionError) as exc_info:
        await sync_blog_posts(payload)

    assert exc_info.value.slug == "same"
    assert exc_info.value.numbers == [1, 2]
    assert set_mock.call_count == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_deletes_orphan_keys(mocker):
    async def fake_existing() -> set[str]:
        return {"kept", "removed"}

    mocker.patch.object(blog_sync, "_existing_post_slugs", side_effect=fake_existing)
    mocker.patch.object(blog_sync.redis_store, "set", new=mocker.AsyncMock())
    delete_mock = mocker.patch.object(blog_sync.redis_store, "delete", new=mocker.AsyncMock())

    d = _make_discussion(body="---\nslug: kept\n---\nBody")
    payload = BlogSyncPayload(discussions=[d])

    await sync_blog_posts(payload)

    delete_calls = [call.args[0] for call in delete_mock.call_args_list]
    assert f"{POST_KEY_PREFIX}removed" in delete_calls
    assert f"{POST_KEY_PREFIX}kept" not in delete_calls


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sync_index_sorted_by_date_descending(mock_redis):
    set_mock, _ = mock_redis
    older = _make_discussion(
        number=1,
        body="---\nslug: older\n---\nA",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer = _make_discussion(
        number=2,
        body="---\nslug: newer\n---\nB",
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    payload = BlogSyncPayload(discussions=[older, newer])

    await sync_blog_posts(payload)

    index_call = next(call for call in set_mock.call_args_list if call.args[0] == INDEX_KEY)
    index_data = json.loads(index_call.args[1])
    assert [e["slug"] for e in index_data] == ["newer", "older"]
