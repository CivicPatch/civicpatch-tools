import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.civicpatch_api import get_posts

pytestmark = pytest.mark.unit

MODULE = "services.civicpatch_api"

_ENV = {"CIVICPATCH_ORG_URL": "https://civicpatch.org"}
_OCDID = "ocd-jurisdiction/country:us/state:ca/county:fresno/government"


def _response(data: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {"data": data}
    response.raise_for_status = MagicMock()
    return response


@pytest.mark.asyncio
async def test_get_posts_reads_the_organizations_endpoint():
    """Posts move under the organization that holds them (civicpatch.org's own routes) — a
    per-jurisdiction posts endpoint no longer exists, and hitting it 404s in production."""
    client = MagicMock()
    client.get = AsyncMock(return_value=_response({"organizations": []}))

    with patch(f"{MODULE}.get_env_vars", return_value=_ENV):
        await get_posts(client, _OCDID)

    client.get.assert_awaited_once_with(
        f"https://civicpatch.org/api/v1/organizations/{_OCDID}"
    )


@pytest.mark.asyncio
async def test_get_posts_flattens_every_organizations_posts():
    client = MagicMock()
    client.get = AsyncMock(
        return_value=_response(
            {
                "organizations": [
                    {"name": "Office of the Mayor", "posts": [{"id": "p1"}]},
                    {"name": "City Council", "posts": [{"id": "p2"}, {"id": "p3"}]},
                ]
            }
        )
    )

    with patch(f"{MODULE}.get_env_vars", return_value=_ENV):
        posts = await get_posts(client, _OCDID)

    assert [post["id"] for post in posts] == ["p1", "p2", "p3"]
