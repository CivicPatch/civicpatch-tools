import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from services.civicpatch_api import get_organizations

pytestmark = pytest.mark.unit

MODULE = "services.civicpatch_api"

_ENV = {"CIVICPATCH_ORG_URL": "https://civicpatch.org"}
_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"


def _response(data: dict) -> MagicMock:
    response = MagicMock()
    response.json.return_value = {"data": data}
    response.raise_for_status = MagicMock()
    return response


def _post(post_id: str, organization_id: str) -> dict:
    return {
        "id": post_id,
        "jurisdiction_ocdid": _OCDID,
        "organization_id": organization_id,
        "role_id": "mayor",
        "division_ocdid": "ocd-division/country:us/state:wa/place:seattle",
        "label": "Mayor",
        "meta_headcount": 1,
        "meta_is_tracked": True,
        "meta_is_verified": False,
    }


@pytest.mark.asyncio
async def test_get_organizations_reads_the_organizations_endpoint():
    """Posts move under the organization that holds them (civicpatch.org's own routes) — a
    per-jurisdiction posts endpoint no longer exists, and hitting it 404s in production."""
    client = MagicMock()
    client.get = AsyncMock(return_value=_response({"organizations": []}))

    with patch(f"{MODULE}.get_env_vars", return_value=_ENV):
        await get_organizations(client, _OCDID)

    client.get.assert_awaited_once_with(
        f"https://civicpatch.org/api/v1/organizations/{_OCDID}"
    )


@pytest.mark.asyncio
async def test_get_organizations_keeps_each_bodys_posts_under_it():
    client = MagicMock()
    client.get = AsyncMock(
        return_value=_response(
            {
                "organizations": [
                    {
                        "id": "mayor-office",
                        "name": "Office of the Mayor",
                        "url": None,
                        "sort_order": 0,
                        "meta_is_default": True,
                        "posts": [_post("p1", "mayor-office")],
                    },
                    {
                        "id": "council",
                        "name": "City Council",
                        "url": None,
                        "sort_order": 1,
                        "meta_is_default": False,
                        "posts": [_post("p2", "council"), _post("p3", "council")],
                    },
                ]
            }
        )
    )

    with patch(f"{MODULE}.get_env_vars", return_value=_ENV):
        organizations = await get_organizations(client, _OCDID)

    assert [(o.name, o.meta_is_default, [p.id for p in o.posts]) for o in organizations] == [
        ("Office of the Mayor", True, ["p1"]),
        ("City Council", False, ["p2", "p3"]),
    ]


@pytest.mark.asyncio
async def test_a_governing_law_source_page_is_stored_through_cp_org_and_read_back_by_id():
    from services.civicpatch_api import get_governing_law_source_page, store_governing_law_source_page

    row = {"id": "row-1", "jurisdiction_ocdid": _OCDID, "source_url": "https://x.gov/charter", "page_hash": "abc", "cache_path": "governing_law/abc.md"}
    client = MagicMock()
    client.post = AsyncMock(return_value=_response(row))
    client.get = AsyncMock(return_value=_response({**row, "text": "§ 1."}))

    with patch(f"{MODULE}.get_env_vars", return_value=_ENV):
        stored = await store_governing_law_source_page(client, _OCDID, "https://x.gov/charter", "§ 1.")
        found = await get_governing_law_source_page(client, _OCDID, "row-1")

    client.post.assert_awaited_once_with(
        f"https://civicpatch.org/api/v1/jurisdictions/{_OCDID}/governing_law_source_pages",
        json={"source_url": "https://x.gov/charter", "text": "§ 1."},
    )
    client.get.assert_awaited_once_with(f"https://civicpatch.org/api/v1/jurisdictions/{_OCDID}/governing_law_source_pages/row-1")
    assert stored == row
    assert found["text"] == "§ 1."
