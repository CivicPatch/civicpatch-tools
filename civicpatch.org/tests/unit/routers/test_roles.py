"""Thin HTTP-contract tests for the role endpoint. Auth is exercised by overriding
get_optional_user per role; the service layer is mocked at the call boundary.

The read runs full-stack in tests/integration/routers/test_roles.py.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lib.auth import get_optional_user
from routers.api import roles as roles_router
from schemas.common import Identity, UserRole
from shared.schemas import Role

_PREFIX = "/roles"


def _identity(role: UserRole) -> Identity:
    return Identity(
        type="cookie",
        provider="supabase",
        provider_user_id="user-uuid",
        email="user@example.com",
        role=role.value,
        user_id="user-1",
    )


def _client(role: UserRole) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: _identity(role)
    app.include_router(roles_router.get_router(), prefix=_PREFIX)
    return TestClient(app)


@pytest.mark.unit
def test_get_roles_happy():
    roles = [Role(id="mayor", label="Mayor", is_unique=False, aliases=["mayor"])]
    with patch(
        "services.role_config.load_roles", new_callable=AsyncMock, return_value=roles
    ):
        response = _client(UserRole.MAINTAINERS).get(_PREFIX, params={"level": "local"})

    assert response.status_code == 200
    assert response.json()["data"]["roles"] == [
        {
            "id": "mayor",
            "label": "Mayor",
            "status": "active",
            "is_unique": False,
            "priority": None,
            "selection_method": "elected_by_voters",
            "aliases": ["mayor"],
        }
    ]


@pytest.mark.unit
def test_get_roles_is_open_to_everyone():
    """The taxonomy is a vocabulary, and the jurisdiction page is public: it needs role labels
    to head a list of posts."""
    roles = [Role(id="mayor", label="Mayor", is_unique=False, aliases=["mayor"])]
    with patch(
        "services.role_config.load_roles", new_callable=AsyncMock, return_value=roles
    ):
        response = _client(UserRole.CONTRIBUTORS).get(_PREFIX, params={"level": "local"})

    assert response.status_code == 200
