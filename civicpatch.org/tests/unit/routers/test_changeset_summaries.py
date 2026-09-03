"""Route-contract tests for the cross-state changeset summary.

Thin on purpose: the arithmetic is locked down in
`tests/integration/database/test_changeset_summaries.py` against real Postgres. What is worth
checking here is the HTTP contract — who may call it, what the query-string bounds are, and
that an unknown bucket is refused rather than answered with an empty page.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from lib.auth import get_optional_user
from routers.api import changeset_summaries as summaries_router
from schemas.changeset_summaries import BucketPage, BucketRow
from schemas.common import Identity, UserRole


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(summaries_router.get_router(), prefix="/summaries")
    return TestClient(app)


def _identity(role: UserRole) -> Identity:
    return Identity(
        type="session",
        provider="github",
        provider_user_id="u1",
        email="u@x.com",
        role=role,
        user_id="user-1",
    )


def _as(client, role: UserRole) -> None:
    client.app.dependency_overrides[get_optional_user] = lambda: _identity(role)


@pytest.mark.unit
@pytest.mark.parametrize(
    "role", [UserRole.DEFAULT, UserRole.CONTRIBUTORS, UserRole.MAINTAINERS]
)
def test_any_signed_in_user_may_read_the_rollup(client, role):
    """Signed-in, like the rest of the Activity section: the underlying rows are already
    public per jurisdiction. Starting a scrape from them is gated separately."""
    _as(client, role)
    with patch.object(summaries_router.db, "get_state_rollup", new=AsyncMock(return_value=[])):
        response = client.get("/summaries/rollup")

    assert response.status_code == 200
    assert response.json() == {"data": []}


@pytest.mark.unit
def test_a_signed_out_visitor_is_refused(client):
    client.app.dependency_overrides[get_optional_user] = lambda: None
    with patch.object(summaries_router.db, "get_state_rollup", new=AsyncMock(return_value=[])):
        response = client.get("/summaries/rollup")

    assert response.status_code in (401, 403)


@pytest.mark.unit
def test_an_unknown_bucket_is_a_404_not_an_empty_page(client):
    """The query fails closed on an unknown bucket, so without this a typo would read as
    "this bucket is empty" and send someone looking for work that exists."""
    _as(client, UserRole.DEFAULT)
    response = client.get("/summaries/buckets/wa/not-a-bucket")

    assert response.status_code == 404


@pytest.mark.unit
def test_a_known_bucket_reaches_the_query_with_its_paging(client):
    _as(client, UserRole.DEFAULT)
    page = BucketPage(
        total=1,
        rows=[
            BucketRow(
                jurisdiction_ocdid="ocd/x",
                jurisdiction_path="ocd/x",
                name="X",
                days_waiting=4,
            )
        ],
    )
    with patch.object(
        summaries_router.db, "get_state_bucket", new=AsyncMock(return_value=page)
    ) as bucket:
        response = client.get("/summaries/buckets/wa/review?limit=10&offset=20")

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1
    assert bucket.await_args.args == ("wa", "review", 10, 20, summaries_router.db.DEFAULT_WINDOW_DAYS)


@pytest.mark.unit
@pytest.mark.parametrize("window", [0, -1, 400])
def test_the_window_is_bounded(client, window):
    """An unbounded window is an unbounded scan for anyone who edits the query string."""
    _as(client, UserRole.DEFAULT)
    with patch.object(summaries_router.db, "get_state_calendar", new=AsyncMock(return_value=[])):
        response = client.get(f"/summaries/calendar?window_days={window}")

    assert response.status_code == 422


@pytest.mark.unit
def test_the_bucket_page_size_is_capped(client):
    """A state holds thousands of jurisdictions; the modal must never load a bucket whole."""
    _as(client, UserRole.DEFAULT)
    response = client.get("/summaries/buckets/wa/review?limit=5000")

    assert response.status_code == 422
