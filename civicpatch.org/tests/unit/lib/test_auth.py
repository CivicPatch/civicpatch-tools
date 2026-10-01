"""Tests for `require_route_access` — the auth decision tree.

We exercise the dependency function directly with constructed Identity objects
rather than going through FastAPI. This isolates the decision logic from the
HTTP layer and lets us pin every (RouteCategory × required_role × identity)
combination cheaply.
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from lib.auth import get_user_by_cookie, require_route_access
from schemas.common import Identity, UserRole, RouteCategory, ServiceKey


def _service_identity() -> Identity:
    """The synthetic Identity built when SERVICE_API_KEY is presented."""
    return Identity(
        type="service_api_key",
        provider="system",
        provider_user_id="service_api_key",
        email="service@civicpatch.org",
    )


def _user_identity(role: str) -> Identity:
    return Identity(
        type="cookie",
        provider="supabase",
        provider_user_id="sb-xyz",
        email="user@example.com",
        role=role,
        user_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    )


# ── PUBLIC ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_public_allows_anonymous():
    dep = require_route_access(RouteCategory.PUBLIC)
    result = await dep(identity=None)
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_public_allows_signed_in_user():
    dep = require_route_access(RouteCategory.PUBLIC)
    identity = _user_identity(UserRole.DEFAULT.value)
    result = await dep(identity=identity)
    assert result is identity


# ── AUTHENTICATED ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_authenticated_rejects_anonymous():
    dep = require_route_access(RouteCategory.AUTHENTICATED)
    with pytest.raises(HTTPException) as exc:
        await dep(identity=None)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.unit
async def test_authenticated_allows_default_user():
    """A signed-in user at the default level still passes AUTHENTICATED."""
    dep = require_route_access(RouteCategory.AUTHENTICATED)
    identity = _user_identity(UserRole.DEFAULT.value)
    assert (await dep(identity=identity)) is identity


# ── SERVICE ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_service_allows_service_api_key():
    dep = require_route_access(RouteCategory.SERVICE)
    identity = _service_identity()
    assert (await dep(identity=identity)) is identity


@pytest.mark.asyncio
@pytest.mark.unit
async def test_service_rejects_human_admin():
    """Even an admin user can't reach a SERVICE-gated route via cookie."""
    dep = require_route_access(RouteCategory.SERVICE)
    identity = _user_identity(UserRole.ADMINS.value)
    with pytest.raises(HTTPException) as exc:
        await dep(identity=identity)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.unit
async def test_service_rejects_anonymous():
    dep = require_route_access(RouteCategory.SERVICE)
    with pytest.raises(HTTPException) as exc:
        await dep(identity=None)
    assert exc.value.status_code == 403


# ── The service key outside SERVICE routes ───────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_service_key_is_refused_by_a_team_route_that_does_not_take_it():
    """No role to check, so it was let through everything, admin routes included. Now it
    reaches only the routes that name it, so a leaked key cannot change anyone's role."""
    dep = require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.ADMINS)
    with pytest.raises(HTTPException) as exc:
        await dep(identity=_service_identity())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.unit
async def test_service_key_is_refused_by_an_authenticated_route_that_does_not_take_it():
    dep = require_route_access(RouteCategory.AUTHENTICATED)
    with pytest.raises(HTTPException) as exc:
        await dep(identity=_service_identity())
    assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize("category", [RouteCategory.AUTHENTICATED, RouteCategory.TEAM_REQUIRED])
async def test_service_key_reaches_a_route_that_takes_it(category: RouteCategory):
    dep = require_route_access(category, UserRole.MAINTAINERS, ServiceKey.ACCEPTED)
    identity = _service_identity()
    assert (await dep(identity=identity)) is identity


@pytest.mark.asyncio
@pytest.mark.unit
async def test_service_key_reads_public_routes():
    dep = require_route_access(RouteCategory.PUBLIC)
    identity = _service_identity()
    assert (await dep(identity=identity)) is identity


# ── TEAM_REQUIRED — full ladder matrix ───────────────────────────────────────

LADDER = [UserRole.DEFAULT, UserRole.CONTRIBUTORS, UserRole.MAINTAINERS, UserRole.ADMINS]


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize("caller_role", LADDER)
@pytest.mark.parametrize("required_role", LADDER)
async def test_team_required_ladder_cascade(caller_role: UserRole, required_role: UserRole):
    """For every (caller, required) pair, callers at-or-above the required level pass."""
    dep = require_route_access(RouteCategory.TEAM_REQUIRED, required_role)
    identity = _user_identity(caller_role.value)
    expected_pass = LADDER.index(caller_role) >= LADDER.index(required_role)
    if expected_pass:
        assert (await dep(identity=identity)) is identity
    else:
        with pytest.raises(HTTPException) as exc:
            await dep(identity=identity)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.unit
async def test_team_required_rejects_anonymous():
    dep = require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.DEFAULT)
    with pytest.raises(HTTPException) as exc:
        await dep(identity=None)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.unit
async def test_team_required_no_role_passes_authenticated_user():
    """`require_route_access(TEAM_REQUIRED, None)` collapses to AUTHENTICATED for
    non-service callers — any signed-in user passes, anonymous does not."""
    dep = require_route_access(RouteCategory.TEAM_REQUIRED, None)
    identity = _user_identity(UserRole.DEFAULT.value)
    assert (await dep(identity=identity)) is identity

    with pytest.raises(HTTPException):
        await dep(identity=None)


# ── Unknown role strings cannot elevate ─────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_unknown_role_string_cannot_elevate_via_team_check():
    """Defense-in-depth: even if a user somehow had an unknown role string
    stored, they can't elevate above default via the ladder check."""
    dep = require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.CONTRIBUTORS)
    identity = _user_identity("super_admin_hacker")
    with pytest.raises(HTTPException) as exc:
        await dep(identity=identity)
    assert exc.value.status_code == 403


# ── Cookie sessions ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.unit
async def test_a_session_whose_user_is_gone_is_refused():
    """It used to build an identity with no `user_id`, which passes AUTHENTICATED and then has
    nobody to attribute a write to."""
    session = {"provider": "supabase", "provider_user_id": "sb-gone", "role": "admins"}
    with (
        patch("lib.auth.session_service.get_session", new=AsyncMock(return_value=session)),
        patch("lib.auth.database.get_user", new=AsyncMock(return_value=None)),
    ):
        with pytest.raises(HTTPException) as exc:
            await get_user_by_cookie(SimpleNamespace(method="GET"), "token")
    assert exc.value.status_code == 401
