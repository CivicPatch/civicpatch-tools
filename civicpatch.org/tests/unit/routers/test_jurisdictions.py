import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from schemas.common import Identity, UserRole
from schemas.jurisdictions import JurisdictionSearchResult
from lib.auth import get_optional_user
from routers.api import jurisdictions as jurisdictions_router


@pytest.fixture(autouse=True)
def always_miss_cache():
    """The search route reads and writes lib.cache; without this, route tests reach a
    real Redis. Always-miss keeps them exercising the uncached path."""
    with patch.object(
        jurisdictions_router.cache_service,
        "get_cached",
        new=AsyncMock(return_value=None),
    ), patch.object(
        jurisdictions_router.cache_service,
        "set_cached",
        new=AsyncMock(return_value=None),
    ):
        yield


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(jurisdictions_router.get_router(), prefix="/jurisdictions")
    return TestClient(app)


def _default():
    return Identity(
        type="session", provider="github", provider_user_id="u2",
        email="d@x.com", role=UserRole.DEFAULT, user_id="user-456",
    )


def _contributor():
    return Identity(
        type="session", provider="github", provider_user_id="u1",
        email="u@x.com", role=UserRole.CONTRIBUTORS, user_id="user-123",
    )


def _maintainer():
    return Identity(
        type="session", provider="github", provider_user_id="u3",
        email="m@x.com", role=UserRole.MAINTAINERS, user_id="user-789",
    )


REQUEST_ID = "2026-07-31-abcd"

PATCH_BODY = {
    "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland",
    "url": "https://oakland.gov",
}


COMMIT_URL = "https://github.com/x/commit/abc123"


@pytest.mark.unit
def test_patch_jurisdiction_data_commits_for_maintainer(client):
    """The edit lands within the request: there is no PR to open and no merge to wait on,
    so the commit url is the whole outcome."""
    client.app.dependency_overrides[get_optional_user] = _maintainer
    with patch(
        "services.jurisdiction_pull_request.commit_jurisdiction_patch",
        new_callable=AsyncMock,
        return_value=(COMMIT_URL, COMMIT_URL, REQUEST_ID),
    ):
        response = client.patch("/jurisdictions/data", json=PATCH_BODY)

    assert response.status_code == 200
    assert response.json()["data"]["open_data_url"] == COMMIT_URL


# The Website field is patched into the jurisdictions repo, so it never passes through
# `Official` and gets none of the people validation. Rejects rather than canonicalizing:
# silently prepending a scheme would publish a typo.
@pytest.mark.unit
@pytest.mark.parametrize(
    "url", ["oakland.gov", "https://oakland", "https://oak land.gov", "ftp://oakland.gov"]
)
def test_patch_jurisdiction_data_rejects_a_malformed_url(client, url):
    client.app.dependency_overrides[get_optional_user] = _maintainer
    with patch(
        "services.jurisdiction_pull_request.commit_jurisdiction_patch",
        new_callable=AsyncMock,
    ) as mock_open:
        response = client.patch("/jurisdictions/data", json={**PATCH_BODY, "url": url})

    assert response.status_code == 422
    mock_open.assert_not_awaited()


# Clearing the website is a legitimate edit, so an empty value is not a malformed one.
@pytest.mark.unit
def test_patch_jurisdiction_data_allows_clearing_the_url(client):
    client.app.dependency_overrides[get_optional_user] = _maintainer
    with (
        patch(
            "services.jurisdiction_pull_request.commit_jurisdiction_patch",
            new_callable=AsyncMock,
            return_value=(42, "https://github.com/x/pull/42", REQUEST_ID),
        ),
    ):
        response = client.patch("/jurisdictions/data", json={**PATCH_BODY, "url": ""})

    assert response.status_code == 200


@pytest.mark.unit
@pytest.mark.parametrize("identity", [_default, _contributor])
def test_patch_jurisdiction_data_requires_maintainer(client, identity):
    # The Jurisdiction Details sidebar edits published data via an auto-merged PR,
    # so it is gated to maintainers alongside the Current tab's people edits.
    client.app.dependency_overrides[get_optional_user] = identity
    with patch(
        "services.jurisdiction_pull_request.commit_jurisdiction_patch",
        new_callable=AsyncMock,
    ) as mock_open:
        response = client.patch("/jurisdictions/data", json=PATCH_BODY)

    assert response.status_code == 403
    mock_open.assert_not_awaited()


@pytest.mark.unit
def test_get_jurisdiction_states_returns_list(client):
    mock_states = [{"code": "ca", "name": "California"}, {"code": "ny", "name": "New York"}]
    with patch(
        "routers.api.jurisdictions.database.get_states_with_names",
        new=AsyncMock(return_value=mock_states),
    ):
        response = client.get("/jurisdictions/states")

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "total_items" in data
    assert data["total_items"] == 2


@pytest.mark.unit
def test_get_jurisdictions_by_ocdids_returns_data(client):
    with patch(
        "database.jurisdictions.get_jurisdictions_by_ocdids",
        new_callable=AsyncMock,
        return_value=[{"id": "ocd-jurisdiction/country:us/state:ca/place:oakland", "name": "Oakland"}],
    ):
        response = client.post(
            "/jurisdictions/by-ocdids",
            json={"ocdids": ["ocd-jurisdiction/country:us/state:ca/place:oakland"]},
        )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert isinstance(data["data"], list)


@pytest.mark.unit
def test_get_jurisdiction_history_returns_data(client):
    with patch(
        "database.jurisdictions.get_jurisdiction_history",
        new_callable=AsyncMock,
        return_value=[{"request_id": "req-1", "status": "complete"}],
    ):
        response = client.get(
            "/jurisdictions/history",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.unit
def test_get_jurisdiction_history_returns_404_when_none(client):
    with patch(
        "database.jurisdictions.get_jurisdiction_history",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get(
            "/jurisdictions/history",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:unknown"},
        )

    assert response.status_code == 404


@pytest.mark.unit
def test_get_jurisdiction_returns_data(client):
    with patch(
        "database.jurisdictions.get_jurisdiction",
        new_callable=AsyncMock,
        return_value={"data": {"id": "ocd-jurisdiction/country:us/state:ca/place:oakland", "name": "Oakland"}, "geo_center": None},
    ):
        response = client.get(
            "/jurisdictions",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.unit
def test_get_jurisdiction_returns_404_when_not_found(client):
    with patch(
        "database.jurisdictions.get_jurisdiction",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get(
            "/jurisdictions",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:unknown"},
        )

    assert response.status_code == 404


# ── GET /jurisdictions/search (nationwide typeahead) ─────────────────────────


def _search_result(**overrides):
    base = dict(
        jurisdiction_ocdid="ocd-jurisdiction/country:us/state:wa/place:seattle/government",
        level="local",
        name="Seattle city",
        display_name=None,
        population=741440,
        parent_names=["King County", "Washington"],
    )
    return JurisdictionSearchResult(**{**base, **overrides})


@pytest.mark.unit
def test_search_returns_total_and_results(client):
    with patch.object(
        jurisdictions_router.database,
        "search_jurisdictions_by_text",
        new=AsyncMock(return_value=(121, [_search_result()])),
    ):
        response = client.get("/jurisdictions/search", params={"q": "seattle wa"})

    assert response.status_code == 200
    body = response.json()
    # Envelope matches /{state}/search so both are one contract for /api/v1 consumers.
    assert set(body) == {"total_items", "page", "total_pages", "limit", "data", "links"}
    assert set(body["links"]) == {"prev", "next", "self"}
    assert body["total_items"] == 121
    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == "Seattle city"
    # state/county are not repeated as scalars — the parent trail carries them instead
    assert set(body["data"][0]) == {
        "jurisdiction_ocdid",
        "level",
        "name",
        "display_name",
        "population",
        "parent_names",
    }
    assert body["data"][0]["parent_names"] == ["King County", "Washington"]


@pytest.mark.unit
def test_search_below_minimum_length_does_not_hit_the_database(client):
    search = AsyncMock(return_value=(0, []))
    with patch.object(
        jurisdictions_router.database, "search_jurisdictions_by_text", new=search
    ), patch.object(
        jurisdictions_router.database,
        "search_jurisdictions_fuzzy",
        new=AsyncMock(return_value=(0, [])),
    ):
        response = client.get("/jurisdictions/search", params={"q": "s"})

    assert response.status_code == 200
    body = response.json()
    assert body["total_items"] == 0 and body["data"] == []
    search.assert_not_awaited()


@pytest.mark.unit
def test_search_without_a_query_does_not_hit_the_database(client):
    search = AsyncMock(return_value=(0, []))
    with patch.object(
        jurisdictions_router.database, "search_jurisdictions_by_text", new=search
    ), patch.object(
        jurisdictions_router.database,
        "search_jurisdictions_fuzzy",
        new=AsyncMock(return_value=(0, [])),
    ):
        response = client.get("/jurisdictions/search")

    assert response.status_code == 200
    body = response.json()
    assert body["total_items"] == 0 and body["data"] == []
    search.assert_not_awaited()


@pytest.mark.unit
def test_search_rejects_an_oversized_limit(client):
    response = client.get(
        "/jurisdictions/search", params={"q": "seattle", "limit": 5000}
    )
    assert response.status_code == 422


@pytest.mark.unit
def test_search_rejects_a_nonpositive_limit(client):
    # LIMIT -1 is a Postgres error; reject at the edge rather than 500 from the driver.
    assert (
        client.get("/jurisdictions/search", params={"q": "x", "limit": 0}).status_code
        == 422
    )
    assert (
        client.get("/jurisdictions/search", params={"q": "x", "limit": -1}).status_code
        == 422
    )


@pytest.mark.unit
def test_search_excludes_state_level_rows(client):
    search = AsyncMock(return_value=(0, []))
    with patch.object(
        jurisdictions_router.database, "search_jurisdictions_by_text", new=search
    ), patch.object(
        jurisdictions_router.database,
        "search_jurisdictions_fuzzy",
        new=AsyncMock(return_value=(0, [])),
    ):
        client.get("/jurisdictions/search", params={"q": "washington"})

    # state rows exist only to supply state names to search_text — never results
    assert "state" not in search.await_args.args[1]


@pytest.mark.unit
def test_search_is_open_to_anonymous_callers(client):
    # No auth override is installed by this test — the route must not require one.
    with patch.object(
        jurisdictions_router.database,
        "search_jurisdictions_by_text",
        new=AsyncMock(return_value=(0, [])),
    ), patch.object(
        jurisdictions_router.database,
        "search_jurisdictions_fuzzy",
        new=AsyncMock(return_value=(0, [])),
    ):
        assert client.get("/jurisdictions/search", params={"q": "seattle"}).status_code == 200


@pytest.mark.unit
def test_search_page_two_offsets_the_query(client):
    search = AsyncMock(return_value=(121, []))
    with patch.object(
        jurisdictions_router.database, "search_jurisdictions_by_text", new=search
    ), patch.object(
        jurisdictions_router.database,
        "search_jurisdictions_fuzzy",
        new=AsyncMock(return_value=(0, [])),
    ):
        client.get(
            "/jurisdictions/search", params={"q": "lake", "limit": 10, "page": 3}
        )

    assert search.await_args.args[3] == 20  # skip = (page - 1) * limit


@pytest.mark.unit
def test_search_links_carry_the_query(client):
    # A next link without q would page a different search entirely.
    with patch.object(
        jurisdictions_router.database,
        "search_jurisdictions_by_text",
        new=AsyncMock(return_value=(121, [_search_result()])),
    ):
        body = client.get(
            "/jurisdictions/search", params={"q": "lake", "limit": 10, "page": 2}
        ).json()

    assert "q=lake" in body["links"]["next"]
    assert "q=lake" in body["links"]["prev"]
    assert "page=3" in body["links"]["next"]
    assert "page=1" in body["links"]["prev"]


@pytest.mark.unit
def test_search_first_page_has_no_prev_and_last_page_has_no_next(client):
    with patch.object(
        jurisdictions_router.database,
        "search_jurisdictions_by_text",
        new=AsyncMock(return_value=(1, [_search_result()])),
    ):
        body = client.get("/jurisdictions/search", params={"q": "seattle"}).json()

    assert body["links"]["prev"] == ""
    assert body["links"]["next"] == ""
    assert body["links"]["self"] != ""


@pytest.mark.unit
def test_search_falls_back_to_fuzzy_only_when_exact_finds_nothing(client):
    exact = AsyncMock(return_value=(0, []))
    fuzzy = AsyncMock(return_value=(1, [_search_result(name="Seattle city")]))
    with patch.object(
        jurisdictions_router.database, "search_jurisdictions_by_text", new=exact
    ), patch.object(
        jurisdictions_router.database, "search_jurisdictions_fuzzy", new=fuzzy
    ):
        body = client.get("/jurisdictions/search", params={"q": "seatle wa"}).json()

    fuzzy.assert_awaited_once()
    assert body["total_items"] == 1
    assert body["data"][0]["name"] == "Seattle city"


@pytest.mark.unit
def test_search_does_not_fall_back_when_exact_finds_anything(client):
    # The tiers are scored differently, so results are never merged.
    exact = AsyncMock(return_value=(1, [_search_result()]))
    fuzzy = AsyncMock(return_value=(99, []))
    with patch.object(
        jurisdictions_router.database, "search_jurisdictions_by_text", new=exact
    ), patch.object(
        jurisdictions_router.database, "search_jurisdictions_fuzzy", new=fuzzy
    ):
        body = client.get("/jurisdictions/search", params={"q": "seattle"}).json()

    fuzzy.assert_not_awaited()
    assert body["total_items"] == 1


@pytest.mark.unit
def test_search_serves_a_cache_hit_without_touching_the_database(client):
    hit = {
        "total_items": 1,
        "page": 1,
        "total_pages": 1,
        "limit": 10,
        "data": [],
        "links": {"prev": "", "next": "", "self": "/api/v1/jurisdictions/search?q=x"},
    }
    search = AsyncMock(return_value=(0, []))
    with patch.object(
        jurisdictions_router.cache_service, "get_cached", new=AsyncMock(return_value=hit)
    ), patch.object(
        jurisdictions_router.database, "search_jurisdictions_by_text", new=search
    ):
        body = client.get("/jurisdictions/search", params={"q": "seattle"}).json()

    search.assert_not_awaited()
    assert body["total_items"] == 1
    # Round-trips through the "self" alias, not the self_link field name.
    assert body["links"]["self"] == "/api/v1/jurisdictions/search?q=x"


@pytest.mark.unit
def test_differently_spelled_queries_share_one_cache_entry(client):
    keys = []
    with patch.object(
        jurisdictions_router.cache_service,
        "get_cached",
        new=AsyncMock(side_effect=lambda key: keys.append(key) or None),
    ), patch.object(
        jurisdictions_router.database,
        "search_jurisdictions_by_text",
        new=AsyncMock(return_value=(1, [_search_result()])),
    ):
        client.get("/jurisdictions/search", params={"q": "Seattle, WA"})
        client.get("/jurisdictions/search", params={"q": "seattle  wa"})

    assert keys[0] == keys[1]
