"""HTTP-contract tests for the posts reads.

Only the bulk read is covered here: it is the one with a shape worth pinning (paging, a state
filter, and a literal path that has to win against a catch-all). The per-jurisdiction read is
exercised full-stack elsewhere.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.auth import get_optional_user
from routers.api import posts as posts_router
from schemas.common import Identity, UserRole

_PREFIX = "/posts"


@pytest.fixture
def client():
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: Identity(
        type="cookie",
        provider="supabase",
        provider_user_id="user-uuid",
        email="user@example.com",
        role=UserRole.MAINTAINERS.value,
        user_id="00000000-0000-4000-8000-000000000001",
    )
    app.include_router(posts_router.get_router(), prefix=_PREFIX)
    return TestClient(app)


@pytest.mark.unit
def test_bulk_pages_a_whole_state(client):
    """One request per page instead of one per jurisdiction — Washington is 281 of them."""
    with patch(
        "routers.api.posts.posts.list_page_for_state",
        new_callable=AsyncMock,
        return_value=(593, [{"id": "1", "post_label": "Council Member"}]),
    ) as list_page:
        response = client.get(f"{_PREFIX}/bulk?state=WA&page=2&per_page=200")

    body = response.json()
    assert response.status_code == 200
    assert body["total_items"] == 593
    assert body["total_pages"] == 3
    # Lowercased for the ocdid LIKE, and the offset follows the page.
    list_page.assert_awaited_once_with("wa", 200, 200)


@pytest.mark.unit
def test_bulk_refuses_a_state_that_is_not_a_code(client):
    """It reaches a LIKE against the ocdid, so it is worth rejecting before the query."""
    assert client.get(f"{_PREFIX}/bulk?state=washington").status_code == 400


@pytest.mark.unit
def test_bulk_requires_a_state(client):
    """Without one this would be every post in the database."""
    assert client.get(f"{_PREFIX}/bulk").status_code == 422
