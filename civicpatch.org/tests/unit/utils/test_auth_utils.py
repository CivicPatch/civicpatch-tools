import pytest
from fastapi import HTTPException
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory

@pytest.mark.asyncio
async def test_dependency_returns_identity_for_public():
    identity = Identity(
        type="cookie",
        provider="test",
        provider_user_id="123",
        email="test@example.com",
        teams=["team1", "team2"]
    )
    dep = require_route_access(RouteCategory.PUBLIC, teams_required=["team1"])
    result = await dep(identity)
    assert result == identity

@pytest.mark.asyncio
async def test_dependency_returns_identity_for_authenticated():
    identity = Identity(
        type="cookie",
        provider="test",
        provider_user_id="123",
        email="test@example.com",
        teams=["team1", "team2"]
    )
    dep = require_route_access(RouteCategory.AUTHENTICATED, teams_required=["team1"])
    result = await dep(identity)
    assert result == identity

@pytest.mark.asyncio
async def test_dependency_returns_identity_for_service():
    identity_service = Identity(
        type="service_api_key",
        provider="system",
        provider_user_id="service_api_key",
        email=None,
        teams=[]
    )
    dep = require_route_access(RouteCategory.SERVICE, teams_required=["team1"])
    result = await dep(identity_service)
    assert result == identity_service

@pytest.mark.asyncio
async def test_dependency_returns_identity_for_team_required():
    identity = Identity(
        type="cookie",
        provider="test",
        provider_user_id="123",
        email="test@example.com",
        teams=["team1", "team2"]
    )
    dep = require_route_access(RouteCategory.TEAM_REQUIRED, teams_required=["team1"])
    result = await dep(identity)
    assert result == identity

@pytest.mark.asyncio
async def test_dependency_team_required_no_teams():
    identity = Identity(
        type="cookie",
        provider="test",
        provider_user_id="123",
        email="test@example.com",
        teams=[]
    )
    dep = require_route_access(RouteCategory.TEAM_REQUIRED, teams_required=["team1"])

    with pytest.raises(HTTPException) as exc:
        await dep(identity)
    assert exc.value.status_code == 403
    assert "required team" in exc.value.detail

@pytest.mark.asyncio
async def test_dependency_team_required_no_teams_required_and_no_user_teams():
    identity = Identity(
        type="cookie",
        provider="test",
        provider_user_id="123",
        email="test@example.com",
        teams=[]
    )
    dep = require_route_access(RouteCategory.TEAM_REQUIRED, teams_required=None)

    with pytest.raises(HTTPException) as exc:
        await dep(identity)
    assert exc.value.status_code == 403
    assert "required team" in exc.value.detail

@pytest.mark.asyncio
async def test_dependency_team_required_user_teams_not_matching():
    identity = Identity(
        type="cookie",
        provider="test",
        provider_user_id="123",
        email="test@example.com",
        teams=["team2"]
    )
    dep = require_route_access(RouteCategory.TEAM_REQUIRED, teams_required=["team1"])

    with pytest.raises(HTTPException) as exc:
        await dep(identity)
    assert exc.value.status_code == 403
    assert "required team" in exc.value.detail

@pytest.mark.asyncio
async def test_dependency_unknown_category_no_identity():
    unknown_category = "UNKNOWN"
    dep = require_route_access(unknown_category, teams_required=None)
    with pytest.raises(HTTPException) as exc:
        await dep(None)
    assert exc.value.status_code == 403
    assert "access to this resource" in exc.value.detail

@pytest.mark.asyncio
async def test_dependency_service_category_non_service_identity():
    identity = Identity(
        type="cookie",
        provider="test",
        provider_user_id="123",
        email="test@example.com",
        teams=["team1"]
    )
    dep = require_route_access(RouteCategory.SERVICE, teams_required=["team1"])
    with pytest.raises(HTTPException) as exc:
        await dep(identity)
    assert exc.value.status_code == 403
    assert "access to this resource" in exc.value.detail