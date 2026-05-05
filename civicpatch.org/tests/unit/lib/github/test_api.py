from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lib.github.api import get_teams


def _mock_response(teams: list) -> MagicMock:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = teams
    return response


def _github_team(name: str, org: str = "CivicPatch") -> dict:
    return {"name": name, "organization": {"login": org}}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_teams_contributor_receives_default():
    teams = [_github_team("contributors")]
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=_mock_response(teams))))
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await get_teams("token")
    assert "contributors" in result
    assert "default" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_teams_maintainer_with_default_no_duplicate():
    teams = [_github_team("maintainers"), _github_team("default")]
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=_mock_response(teams))))
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await get_teams("token")
    assert result.count("default") == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_teams_no_civicpatch_teams_returns_empty():
    teams = [_github_team("some-team", org="OtherOrg")]
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock(get=AsyncMock(return_value=_mock_response(teams))))
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        result = await get_teams("token")
    assert result == []
