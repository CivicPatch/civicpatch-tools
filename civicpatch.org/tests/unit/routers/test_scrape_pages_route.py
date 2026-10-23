"""The pages a scrape read are for maintainers and above: who `GET …/{changeset_id}/pages` lets in."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.security import APIKeyHeader
from fastapi.testclient import TestClient

from lib.auth import get_optional_user
from routers.api import review_cards
from schemas.common import Identity, UserRole

pytestmark = pytest.mark.unit

_PREFIX = "/api/v1/reviews"
_PATH = f"{_PREFIX}/changeset-1/pages"


def _identity(role: UserRole) -> Identity:
    return Identity(type="user_key", provider="p", provider_user_id="u", email=None, role=role.value, user_id="u-1")


def _client(identity: Identity | None) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: identity
    app.include_router(review_cards.get_router(APIKeyHeader(name="Authorization", auto_error=False)), prefix=_PREFIX)
    return TestClient(app)


def _no_pages():
    return patch.object(review_cards.source_pages_db, "get_scrape_pages", AsyncMock(return_value=[]))


def test_a_maintainer_sees_a_scrapes_pages():
    with _no_pages():
        response = _client(_identity(UserRole.MAINTAINERS)).get(_PATH)

    assert response.status_code == 200


@pytest.mark.parametrize("identity", [None, _identity(UserRole.DEFAULT), _identity(UserRole.CONTRIBUTORS)])
def test_everyone_below_a_maintainer_is_refused(identity):
    with _no_pages():
        response = _client(identity).get(_PATH)

    assert response.status_code == 403
