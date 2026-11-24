from unittest.mock import AsyncMock, patch
from urllib.robotparser import RobotFileParser

import pytest

import services.polite as polite

pytestmark = pytest.mark.unit

_GROUNDING = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/AUZIYQabc"


def _rules(text: str) -> RobotFileParser:
    rules = RobotFileParser()
    rules.parse(text.splitlines())
    return rules


def test_only_geminis_redirect_paths_are_grounding_redirects():
    assert polite.is_grounding_redirect(_GROUNDING)
    assert not polite.is_grounding_redirect("https://vertexaisearch.cloud.google.com/other")
    assert not polite.is_grounding_redirect("https://example.gov/grounding-api-redirect/x")


@pytest.mark.asyncio
async def test_a_grounding_redirect_is_followed_although_its_host_disallows_bots():
    disallowing = _rules("User-agent: *\nDisallow: /grounding-api-redirect\n")
    with patch.object(polite, "robots_of", new=AsyncMock(return_value=disallowing)) as robots:
        await polite.obey_host(_GROUNDING)

    robots.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_page_a_redirect_leads_to_still_answers_to_its_robots():
    disallowing = _rules("User-agent: *\nDisallow: /\n")
    with patch.object(polite, "robots_of", new=AsyncMock(return_value=disallowing)):
        with pytest.raises(polite.DisallowedByRobots):
            await polite.obey_host("https://example.gov/charter.pdf")
