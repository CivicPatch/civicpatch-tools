import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from schemas.common import Identity, UserRole
from schemas.jurisdictions import GovernmentFormSummary, JurisdictionSearchResult
from shared.schemas import GovernmentForm
from lib.auth import get_optional_user
from routers.api import jurisdictions as jurisdictions_router
from database.changesets import WaitingPullRequest
from database.users import SYSTEM_USER_ID
from shared.utils.statuses import PullRequestLabel
import services.jurisdiction_pull_request as jurisdiction_pr_service


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


@pytest.fixture(autouse=True)
def no_form_options_or_waiting_pull_request():
    """The jurisdiction GET also asks for the form options and a waiting PR; both read the DB."""
    with patch(
        "services.government_form.government_form_options", new_callable=AsyncMock, return_value=[]
    ), patch(
        "services.government_form.changesets_db.get_open_jurisdiction_pull_request",
        new_callable=AsyncMock,
        return_value=None,
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


CHANGESET_ID = "2026-07-31-abcd"

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
def test_get_jurisdiction_activity_returns_a_paged_envelope(client):
    """`total_items` / `page` / `total_pages` / `data` — the same shape `/change-logs` and the
    pipeline-run listings return, so a caller learns one envelope rather than three."""
    with patch(
        "database.jurisdictions.get_jurisdiction_activity",
        new_callable=AsyncMock,
        return_value=(60, [{"changeset_id": "req-1", "status": "complete"}]),
    ):
        response = client.get(
            "/jurisdictions/activity",
            params={
                "jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland",
                "page": 2,
                "per_page": 25,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total_items"] == 60
    assert body["page"] == 2
    assert body["total_pages"] == 3
    assert body["data"] == [{"changeset_id": "req-1", "status": "complete"}]


@pytest.mark.unit
def test_a_jurisdiction_with_no_history_is_an_empty_page_not_a_404(client):
    """Replaces `test_get_jurisdiction_activity_returns_404_when_none`, which mocked the query
    to return None to reach a branch it could not produce — it answers a list, empty for an
    unknown jurisdiction, which `test_get_jurisdiction_activity_not_found` asserts directly.
    An empty collection is a 200 with nothing in it."""
    with patch(
        "database.jurisdictions.get_jurisdiction_activity",
        new_callable=AsyncMock,
        return_value=(0, []),
    ):
        response = client.get(
            "/jurisdictions/activity",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:unknown"},
        )

    assert response.status_code == 200
    assert response.json()["data"] == []
    assert response.json()["total_pages"] == 1


@pytest.mark.unit
def test_get_jurisdiction_returns_data(client):
    with patch(
        "database.jurisdictions.get_jurisdiction",
        new_callable=AsyncMock,
        return_value={"data": {"id": "ocd-jurisdiction/country:us/state:ca/place:oakland", "name": "Oakland"}, "geo_center": None},
    ), patch(
        "services.government_form.government_form_summary", new_callable=AsyncMock, return_value=None
    ):
        response = client.get(
            "/jurisdictions",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland"},
        )

    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["government_form"] is None


@pytest.mark.unit
def test_get_jurisdiction_returns_its_government_form(client):
    summary = GovernmentFormSummary(
        value=GovernmentForm.OPEN_TOWN_MEETING,
        name="Open town meeting",
        description="a select board or board of selectmen, with an open town meeting",
    )
    with patch(
        "database.jurisdictions.get_jurisdiction",
        new_callable=AsyncMock,
        return_value={"data": {"id": "ocd-jurisdiction/country:us/state:ma/place:millbury", "name": "Millbury"}},
    ), patch(
        "services.government_form.government_form_summary", new_callable=AsyncMock, return_value=summary
    ):
        response = client.get(
            "/jurisdictions",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ma/place:millbury"},
        )

    assert response.json()["government_form"] == {
        "value": "open_town_meeting",
        "name": "Open town meeting",
        "description": "a select board or board of selectmen, with an open town meeting",
    }


@pytest.mark.unit
def test_get_jurisdiction_returns_its_waiting_pull_request(client):
    waiting = WaitingPullRequest(changeset_id=CHANGESET_ID, pull_request_url="https://example.test/pull/7")
    with patch(
        "database.jurisdictions.get_jurisdiction",
        new_callable=AsyncMock,
        return_value={"data": {"id": "ocd-jurisdiction/country:us/state:wa/place:seattle", "name": "Seattle"}},
    ), patch(
        "services.government_form.government_form_summary", new_callable=AsyncMock, return_value=None
    ), patch(
        "services.government_form.changesets_db.get_open_jurisdiction_pull_request",
        new_callable=AsyncMock,
        return_value=waiting,
    ):
        response = client.get(
            "/jurisdictions", params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:wa/place:seattle"}
        )

    assert response.json()["open_pull_request_url"] == "https://example.test/pull/7"


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
        "url",
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


@pytest.mark.unit
def test_in_flight_answers_the_data_envelope(client):
    """Thin on purpose: what the two lanes contain is
    `tests/integration/database/test_jurisdiction_in_flight.py`'s subject. This is the wiring."""
    payload = {"in_flight": [], "last_published_at": None, "total_changesets": 0}
    with patch(
        "database.changesets.get_in_flight",
        new_callable=AsyncMock,
        return_value=payload,
    ):
        response = client.get(
            "/jurisdictions/in-flight",
            params={"jurisdiction_ocdid": "ocd-jurisdiction/country:us/state:ca/place:oakland"},
        )

    assert response.status_code == 200
    assert response.json()["data"] == payload


EDIT_OCDID = "ocd-jurisdiction/country:us/state:ca/place:oakland"
EDIT_URL = f"/jurisdictions/{EDIT_OCDID}/roster-edits"
EDIT_BODY = {"people": [{"id": "p1", "fields": {"name": "Ann Lee-Park"}, "posts": []}]}


@pytest.mark.unit
def test_posting_an_edit_returns_the_changeset_it_was_filed_under(client):
    """The id is the whole outcome: undoing the edit is rolling that changeset back."""
    client.app.dependency_overrides[get_optional_user] = _maintainer
    with patch.object(
        jurisdictions_router.roster_edits,
        "edit_published_roster",
        new=AsyncMock(return_value=CHANGESET_ID),
    ) as edit:
        response = client.post(EDIT_URL, json=EDIT_BODY)

    assert response.status_code == 200, response.text
    assert response.json() == {"data": {"changeset_id": CHANGESET_ID}}
    assert edit.await_args.args[0] == EDIT_OCDID
    assert [person.id for person in edit.await_args.args[1]] == ["p1"]


@pytest.mark.unit
def test_an_edit_with_no_author_is_refused(client):
    """`claims.created_by` is NOT NULL, so the service raises rather than filing a claim
    nobody made."""
    client.app.dependency_overrides[get_optional_user] = _maintainer
    with patch.object(
        jurisdictions_router.roster_edits,
        "edit_published_roster",
        new=AsyncMock(side_effect=jurisdictions_router.roster_edits.AnonymousEdit("x")),
    ):
        response = client.post(EDIT_URL, json=EDIT_BODY)

    assert response.status_code == 401, response.text


@pytest.mark.unit
def test_anyone_signed_in_may_edit_inside_their_own_review(client):
    """A review is open to any signed-in user, and an edit made during one is part of it."""
    client.app.dependency_overrides[get_optional_user] = _default
    with patch.object(
        jurisdictions_router.roster_edits,
        "edit_in_review",
        new=AsyncMock(return_value=CHANGESET_ID),
    ) as save:
        response = client.post(EDIT_URL, json={**EDIT_BODY, "changeset_id": CHANGESET_ID})

    assert response.status_code == 200, response.text


@pytest.mark.unit
def test_editing_the_published_roster_still_needs_a_maintainer(client):
    """No changeset means it publishes on the spot, which is what `PATCH /people/data` was."""
    client.app.dependency_overrides[get_optional_user] = _default

    response = client.post(EDIT_URL, json=EDIT_BODY)

    assert response.status_code == 403, response.text


@pytest.mark.unit
def test_saving_inside_a_review_publishes_nothing(client):
    """A reviewer must be able to put work down half-finished. Approving the review is its own
    act, on its own route."""
    client.app.dependency_overrides[get_optional_user] = _default
    with patch.object(
        jurisdictions_router.roster_edits,
        "edit_published_roster",
        new=AsyncMock(return_value=CHANGESET_ID),
    ) as publish, patch.object(
        jurisdictions_router.roster_edits,
        "edit_in_review",
        new=AsyncMock(return_value=CHANGESET_ID),
    ):
        client.post(EDIT_URL, json={**EDIT_BODY, "changeset_id": CHANGESET_ID})

    publish.assert_not_awaited()


@pytest.mark.unit
def test_an_invalid_field_is_a_422_with_the_failures(client):
    """Moved from `test_review.py::test_save_and_merge_rejects_invalid_field`: the claim is the
    same, the route that makes it is new."""
    client.app.dependency_overrides[get_optional_user] = _default
    failures = [{"id": "p1", "name": "Ann", "field": "emails", "message": "bad"}]
    with patch.object(
        jurisdictions_router.roster_edits,
        "edit_in_review",
        new=AsyncMock(
            side_effect=jurisdictions_router.PeopleValidationError(failures)
        ),
    ):
        response = client.post(EDIT_URL, json={**EDIT_BODY, "changeset_id": CHANGESET_ID})

    assert response.status_code == 422, response.text
    assert response.json()["detail"] == failures


@pytest.mark.unit
def test_an_unknown_post_is_a_404(client):
    """Carried from `memberships.assign`'s 404: the fold ignores a claim naming a post it
    cannot find, so a typo'd id would otherwise file a claim and do nothing silently."""
    client.app.dependency_overrides[get_optional_user] = _default
    with patch.object(
        jurisdictions_router.roster_edits,
        "edit_in_review",
        new=AsyncMock(
            side_effect=jurisdictions_router.roster_edits.UnknownPost(["nope"])
        ),
    ):
        response = client.post(EDIT_URL, json={**EDIT_BODY, "changeset_id": CHANGESET_ID})

    assert response.status_code == 404, response.text


# ── POST /jurisdictions/{ocdid}/pull_requests ─────────────────────────────────
#
# Every jurisdictions.yml edit, url and government form alike: a PR a person merges. The url
# tests were the PATCH /jurisdictions/data tests until url edits moved onto pull requests.

PULL_REQUEST_OCDID = "ocd-jurisdiction/country:us/state:wa/place:seattle/government"
PULL_REQUEST_URL = f"/jurisdictions/{PULL_REQUEST_OCDID}/pull_requests"
PULL_REQUEST_BODY = {"government_form": "mayor_council", "sources": ["https://seattle.gov"]}


def _service_key():
    return Identity(type="service_api_key", provider="system", provider_user_id="service_api_key", email=None)


def _signed_in_without_a_user_row():
    return Identity(type="cookie", provider="github", provider_user_id="u9", email="x@x.com", role=UserRole.MAINTAINERS)


def _opened():
    return jurisdiction_pr_service.OpenedPullRequest(
        pull_request_number=7, pull_request_url="https://example.test/pull/7", changeset_id=CHANGESET_ID
    )


def _post(client, body, identity):
    client.app.dependency_overrides[get_optional_user] = identity
    with patch.object(
        jurisdiction_pr_service, "open_jurisdiction_pull_request", new=AsyncMock(return_value=_opened())
    ) as mock_open:
        response = client.post(PULL_REQUEST_URL, json=body)
    return response, mock_open


@pytest.mark.unit
def test_a_maintainer_opens_a_pull_request_labelled_as_a_maintainer(client):
    response, mock_open = _post(client, PULL_REQUEST_BODY, _maintainer)

    assert response.status_code == 201
    assert response.json()["data"]["pull_request_number"] == 7
    _ocdid, edit, label, author = mock_open.call_args.args
    assert (edit.government_form, label, author) == (GovernmentForm.MAYOR_COUNCIL, PullRequestLabel.MAINTAINER, "user-789")


@pytest.mark.unit
def test_the_pipeline_opens_one_as_the_system_user(client):
    response, mock_open = _post(client, PULL_REQUEST_BODY, _service_key)

    assert response.status_code == 201
    assert mock_open.call_args.args[2:] == (PullRequestLabel.SYSTEM, SYSTEM_USER_ID)


@pytest.mark.unit
def test_a_url_edit_carries_only_the_fields_sent(client):
    response, mock_open = _post(client, {"url": "https://seattle.gov/new"}, _maintainer)

    assert response.status_code == 201
    edit = mock_open.call_args.args[1]
    assert (edit.patch, edit.government_form) == ({"url": "https://seattle.gov/new"}, None)


@pytest.mark.unit
def test_clearing_the_url_is_an_edit(client):
    """An emptied input arrives as "" and is sent as null, which clears the field."""
    response, mock_open = _post(client, {"url": ""}, _maintainer)

    assert response.status_code == 201
    assert mock_open.call_args.args[1].patch == {"url": None}


# The url is patched into the jurisdictions repo, so it never passes through `Official` and
# gets none of the people validation. Rejected rather than canonicalized: silently prepending a
# scheme would publish a typo.
@pytest.mark.unit
@pytest.mark.parametrize("url", ["oakland.gov", "https://oakland", "https://oak land.gov", "ftp://oakland.gov"])
def test_a_malformed_url_is_rejected(client, url):
    response, mock_open = _post(client, {"url": url}, _maintainer)

    assert response.status_code == 422
    mock_open.assert_not_awaited()


@pytest.mark.unit
def test_a_request_naming_no_field_is_rejected(client):
    response, mock_open = _post(client, {"sources": ["https://seattle.gov"]}, _maintainer)

    assert response.status_code == 422
    mock_open.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.parametrize("identity", [_default, _contributor])
def test_it_needs_a_maintainer(client, identity):
    response, mock_open = _post(client, PULL_REQUEST_BODY, identity)

    assert response.status_code == 403
    mock_open.assert_not_awaited()


@pytest.mark.unit
def test_a_person_with_no_user_row_cannot_pass_as_the_system(client):
    response, mock_open = _post(client, PULL_REQUEST_BODY, _signed_in_without_a_user_row)

    assert response.status_code == 401
    mock_open.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.parametrize(
    "error, status",
    [
        (jurisdiction_pr_service.UnknownJurisdiction("x"), 404),
        (jurisdiction_pr_service.NothingToChange("x"), 400),
        (jurisdiction_pr_service.GovernmentFormNotAtLevel("x"), 422),
        (jurisdiction_pr_service.PullRequestAlreadyOpen("https://example.test/pull/6"), 409),
        (jurisdiction_pr_service.PullRequestFailed("x"), 502),
    ],
)
def test_each_refusal_has_its_status(client, error, status):
    client.app.dependency_overrides[get_optional_user] = _maintainer
    with patch.object(jurisdiction_pr_service, "open_jurisdiction_pull_request", new=AsyncMock(side_effect=error)):
        assert client.post(PULL_REQUEST_URL, json=PULL_REQUEST_BODY).status_code == status
