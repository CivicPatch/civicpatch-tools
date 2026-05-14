import json

import pytest

from lib import blog
from lib.blog import INDEX_KEY, POST_KEY_PREFIX, get_all_posts, get_post


def _post_json(slug: str = "hello") -> str:
    return json.dumps(
        {
            "slug": slug,
            "title": "Hello",
            "date": "2026-05-14",
            "description": "hi",
            "author": "shelltr",
            "draft": False,
            "updated_at": "2026-05-14",
            "content_html": "<p>hi</p>",
            "toc_html": "",
            "discussion_url": "https://github.com/x/y/discussions/1",
        }
    )


def _index_json() -> str:
    return json.dumps(
        [
            {
                "slug": "newer",
                "title": "Newer",
                "date": "2026-03-01",
                "description": "n",
                "author": "shelltr",
            },
            {
                "slug": "older",
                "title": "Older",
                "date": "2026-01-01",
                "description": "o",
                "author": "shelltr",
            },
        ]
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_post_returns_blog_post_when_key_present(mocker):
    mocker.patch.object(blog.redis_store, "get", new=mocker.AsyncMock(return_value=_post_json("hello")))
    post = await get_post("hello")
    assert post is not None
    assert post.slug == "hello"
    assert post.title == "Hello"
    assert post.content_html == "<p>hi</p>"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_post_returns_none_when_key_missing(mocker):
    mocker.patch.object(blog.redis_store, "get", new=mocker.AsyncMock(return_value=None))
    assert await get_post("missing") is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_post_uses_correct_key(mocker):
    get_mock = mocker.patch.object(blog.redis_store, "get", new=mocker.AsyncMock(return_value=None))
    await get_post("volunteer")
    get_mock.assert_called_once_with(f"{POST_KEY_PREFIX}volunteer")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_all_posts_returns_entries_when_index_present(mocker):
    mocker.patch.object(blog.redis_store, "get", new=mocker.AsyncMock(return_value=_index_json()))
    posts = await get_all_posts()
    assert len(posts) == 2
    assert [p.slug for p in posts] == ["newer", "older"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_all_posts_returns_empty_when_index_missing(mocker):
    mocker.patch.object(blog.redis_store, "get", new=mocker.AsyncMock(return_value=None))
    assert await get_all_posts() == []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_all_posts_uses_correct_key(mocker):
    get_mock = mocker.patch.object(blog.redis_store, "get", new=mocker.AsyncMock(return_value=None))
    await get_all_posts()
    get_mock.assert_called_once_with(INDEX_KEY)
