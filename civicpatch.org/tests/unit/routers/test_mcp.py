"""The MCP server: its tools through an in-process client, and who `/mcp` lets in.

Tools are thin, so these check wiring and shape; what the reads return is tested where the
queries and the comparison are."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import mcp
import pytest
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.testclient import TestClient

from routers import mcp as mcp_router
from schemas.common import ApiKeyScope, Identity, UserRole
from schemas.jurisdictions import JurisdictionSearchResult
from schemas.roster_comparisons import (
    ComparedField,
    ComparisonRates,
    FieldFilter,
    PeopleFilter,
    PersonOutcome,
    RosterComparisonCreated,
    RosterComparisonDraft,
    RosterComparisonListPage,
    RosterComparisonRun,
    RosterComparisonSummary,
    RunPeoplePage,
    UploadedRow,
)
from services.roster_comparison import RunNotFound
from shared.schemas import Person

_INSTANCE = "https://civicpatch.test"
_RUN_ID = "11111111-1111-1111-1111-111111111111"
_OCDID = "ocd-jurisdiction/country:us/state:vt/place:barre/government"


def _run() -> RosterComparisonRun:
    return RosterComparisonRun(
        id=_RUN_ID, state="vt", started_by_user_id="u", started_at="2026-10-22T00:00:00+00:00",
        source_columns={}, corrections=[], rates=ComparisonRates(), jurisdictions_not_named=0,
    )


@pytest.mark.asyncio
@pytest.mark.unit
async def test_the_server_lists_its_read_tools_and_names_itself_in_the_instructions():
    async with mcp.Client(mcp_router.build_server(_INSTANCE)) as client:
        tools = {tool.name for tool in (await client.list_tools()).tools}
        instructions = client.instructions

    assert tools == {
        "find_jurisdiction",
        "get_jurisdiction_people",
        "list_roster_comparisons",
        "get_roster_comparison",
        "get_roster_comparison_jurisdiction",
        "get_roster_comparison_people",
        "start_roster_comparison",
        "add_roster_comparison_rows",
        "finish_roster_comparison",
        "list_jurisdictions",
    }
    assert f"{_INSTANCE}/api/v1/roster-comparisons" in (instructions or "")
    assert "$CIVICPATCH_API_KEY" in (instructions or "")
    assert "list_jurisdictions" in (instructions or "")
    assert f"{_INSTANCE}/api/v1/jurisdictions/search?state=<state>&limit={mcp_router.LIST_PAGE_SIZE}" in (instructions or "")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_a_runs_summary_is_the_routes_summary():
    summary = RosterComparisonSummary(run=_run(), page_url=f"{_INSTANCE}/roster-comparisons/{_RUN_ID}", jurisdictions=[])
    with patch.object(mcp_router.roster_comparisons, "get_run_summary", AsyncMock(return_value=summary)) as get:
        result = await mcp_router.get_roster_comparison(_RUN_ID)

    get.assert_awaited_once_with(_RUN_ID)
    assert result == summary.model_dump(mode="json")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_listing_runs_is_the_routes_list_with_its_page_size_capped():
    listed = RosterComparisonListPage(total_items=0, page=1, total_pages=1, data=[])
    with patch.object(mcp_router.roster_comparisons, "list_runs", AsyncMock(return_value=listed)) as list_runs:
        result = await mcp_router.list_roster_comparisons(page=0, per_page=5000)

    list_runs.assert_awaited_once_with(1, mcp_router.RUN_PAGE_LIMIT)
    assert result == listed.model_dump(mode="json")


def _caller() -> Identity:
    return Identity(
        type="user_key", provider="p", provider_user_id="u", email=None, role=UserRole.MAINTAINERS.value, user_id="u-1"
    )


def _ctx(identity) -> SimpleNamespace:
    """What a tool's Context carries: the request the gated `/mcp` route forwarded."""
    state = SimpleNamespace(**{mcp_router.CALLER_STATE: identity})
    return SimpleNamespace(request_context=SimpleNamespace(request=SimpleNamespace(state=state)))


@pytest.mark.unit
def test_the_caller_is_the_user_the_gate_let_in():
    assert mcp_router.caller_id(_ctx(_caller())) == _caller().user_id


@pytest.mark.unit
def test_a_request_without_a_caller_is_refused():
    with pytest.raises(PermissionError):
        mcp_router.caller_id(_ctx(None))


@pytest.mark.asyncio
@pytest.mark.unit
async def test_a_batch_of_rows_goes_to_the_callers_draft():
    caller = _caller()
    draft = RosterComparisonDraft(id="d", rows=1, expires_at="2026-10-24T00:00:00+00:00")
    row = {"source_row": 2, "jurisdiction_ocdid": "ocd-jurisdiction/x", "name": "Jane Doe"}
    with patch.object(mcp_router.drafts, "add_draft_rows", AsyncMock(return_value=draft)) as add:
        result = await mcp_router.add_roster_comparison_rows("d", [UploadedRow.model_validate(row)], _ctx(caller))

    draft_id, rows, owner = add.await_args.args
    assert (draft_id, [r.name for r in rows], owner) == ("d", ["Jane Doe"], caller.user_id)
    assert result == draft.model_dump(mode="json")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_finishing_is_the_routes_finish_for_the_caller():
    caller = _caller()
    created = RosterComparisonCreated(id=_RUN_ID, page_url="p", rates=ComparisonRates())
    with patch.object(mcp_router.drafts, "finish_draft", AsyncMock(return_value=created)) as finish:
        result = await mcp_router.finish_roster_comparison("d", [], _ctx(caller))

    finish.assert_awaited_once_with("d", caller.user_id, [])
    assert result["id"] == _RUN_ID


@pytest.mark.asyncio
@pytest.mark.unit
async def test_an_unknown_run_is_an_error_the_agent_can_read():
    missing = AsyncMock(side_effect=RunNotFound(_RUN_ID))
    with patch.object(mcp_router.roster_comparisons, "get_run_people", missing):
        with pytest.raises(RunNotFound, match="No roster comparison"):
            await mcp_router.get_roster_comparison_jurisdiction(_RUN_ID, "ocd-jurisdiction/x")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_the_people_tool_keeps_page_and_size_in_range():
    page = RunPeoplePage(total_items=0, page=1, total_pages=1, data=[])
    with patch.object(mcp_router.roster_comparisons, "get_run_people_page", AsyncMock(return_value=page)) as get:
        await mcp_router.get_roster_comparison_people(
            _RUN_ID, field=ComparedField.EMAILS, level=FieldFilter.CONFLICT, page=0, per_page=5000
        )

    people_filter = PeopleFilter(field=ComparedField.EMAILS, level=FieldFilter.CONFLICT)
    get.assert_awaited_once_with(_RUN_ID, people_filter, 1, mcp_router.PEOPLE_PAGE_LIMIT)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_the_people_tool_lists_one_outcome():
    page = RunPeoplePage(total_items=0, page=1, total_pages=1, data=[])
    with patch.object(mcp_router.roster_comparisons, "get_run_people_page", AsyncMock(return_value=page)) as get:
        await mcp_router.get_roster_comparison_people(_RUN_ID, outcome=PersonOutcome.ONLY_IN_UPLOADED_DATA)

    get.assert_awaited_once_with(_RUN_ID, PeopleFilter(outcome=PersonOutcome.ONLY_IN_UPLOADED_DATA), 1, 50)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_people_come_back_as_the_routes_people_model():
    person = Person(id="p1", name="Jane Doe", jurisdiction_ocdid=_OCDID)
    roster = {"data": [person], "page_url": f"{_INSTANCE}/{_OCDID}"}
    with patch.object(mcp_router, "current_roster", AsyncMock(return_value=roster)):
        result = await mcp_router.get_jurisdiction_people(_OCDID)

    assert result == {"page_url": f"{_INSTANCE}/{_OCDID}", "data": [person.model_dump(mode="json")]}


@pytest.mark.asyncio
@pytest.mark.unit
async def test_find_jurisdiction_searches_the_lowercased_state():
    found = JurisdictionSearchResult(jurisdiction_ocdid=_OCDID, level="local", name="Barre")
    with patch.object(mcp_router, "search_in_state", AsyncMock(return_value=(1, [found]))) as search:
        result = await mcp_router.find_jurisdiction("VT", "Barre")

    search.assert_awaited_once_with("vt", "Barre", mcp_router.SEARCH_LIMIT, 0)
    assert result == [found.model_dump(mode="json")]


# ── the real path: gated route → SDK app (host check, session manager) ───────

_TESTSERVER = "http://testserver"  # TestClient's host, so the SDK's host check passes
_MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Authorization": "Bearer cp_key"}


def _real_mcp_client() -> TestClient:
    server = mcp_router.build_server(_TESTSERVER)
    mcp_app = mcp_router.build_asgi_app(server, _TESTSERVER, [])

    @asynccontextmanager
    async def lifespan(_app):
        async with server.session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan)
    app.include_router(mcp_router.get_router(mcp_app))
    return TestClient(app)


def _rpc(method: str, request_id: int, params: dict | None = None) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}}


@pytest.mark.unit
def test_a_maintainer_lists_the_tools_over_http():
    initialize = _rpc("initialize", 1, {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    })
    with _key_lookup(_user(UserRole.MAINTAINERS)), _real_mcp_client() as client:
        assert client.post("/mcp", json=initialize, headers=_MCP_HEADERS).status_code == 200
        listed = client.post("/mcp", json=_rpc("tools/list", 2), headers=_MCP_HEADERS)

    assert listed.status_code == 200
    names = {tool["name"] for tool in listed.json()["result"]["tools"]}
    assert "get_roster_comparison" in names


@pytest.mark.unit
def test_a_request_for_another_host_is_refused_by_the_sdk():
    with _key_lookup(_user(UserRole.MAINTAINERS)), _real_mcp_client() as client:
        response = client.post("/mcp", json=_rpc("tools/list", 1), headers={**_MCP_HEADERS, "Host": "evil.example"})

    assert response.status_code in (400, 421)


@pytest.mark.unit
def test_allowed_hosts_are_ours_and_local_dev():
    assert mcp_router.allowed_hosts("https://civicpatch.org", []) == ["civicpatch.org", "localhost:*", "127.0.0.1:*"]


@pytest.mark.unit
def test_allowed_hosts_add_configured_extras():
    hosts = mcp_router.allowed_hosts("http://localhost:8000", ["devbox.example.ts.net:8443"])

    assert hosts[-1] == "devbox.example.ts.net:8443"


# ── who /mcp lets in: the real `get_user` → `require_route_access`, only the key lookup mocked ──

async def _inner_app(scope, receive, send):
    await PlainTextResponse("through")(scope, receive, send)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(mcp_router.get_router(_inner_app))
    return TestClient(app)


async def _echo_caller(scope, receive, send):
    caller = getattr(Request(scope).state, mcp_router.CALLER_STATE)
    await PlainTextResponse(caller.user_id)(scope, receive, send)


def _user(role: UserRole) -> dict:
    return {
        "provider": "p",
        "provider_user_id": "u",
        "email": None,
        "role": role.value,
        "id": "u-1",
        "key_scope": ApiKeyScope.FULL.value,
        "key_id": 1,
    }


def _key_lookup(user: dict | None):
    return patch("lib.auth.database.get_user_by_api_key", AsyncMock(return_value=user))


@pytest.fixture(autouse=True)
def _no_last_used_write():
    with patch("lib.auth.database.touch_api_key", new_callable=AsyncMock):
        yield


@pytest.mark.unit
def test_no_key_is_refused_as_every_gated_route_refuses():
    # 403, the shared gate's answer; a 401 would also send MCP clients looking for OAuth.
    assert _client().post("/mcp").status_code == 403


@pytest.mark.unit
def test_an_unknown_or_revoked_key_is_refused():
    with _key_lookup(None):
        response = _client().post("/mcp", headers={"Authorization": "Bearer cp_nope"})

    assert response.status_code == 403


@pytest.mark.unit
def test_a_contributors_key_is_403():
    with _key_lookup(_user(UserRole.CONTRIBUTORS)):
        response = _client().post("/mcp", headers={"Authorization": "Bearer cp_key"})

    assert response.status_code == 403


@pytest.mark.unit
@pytest.mark.parametrize("authorization", ["Bearer cp_key", "cp_key"])
def test_a_maintainers_key_reaches_the_mcp_app_bare_or_bearer(authorization: str):
    with _key_lookup(_user(UserRole.MAINTAINERS)) as lookup:
        response = _client().post("/mcp", headers={"Authorization": authorization})

    assert (response.status_code, response.text) == (200, "through")
    lookup.assert_awaited_once_with("cp_key")


@pytest.mark.unit
def test_the_gate_leaves_the_checked_caller_on_the_request_for_the_tools():
    app = FastAPI()
    app.include_router(mcp_router.get_router(_echo_caller))
    with _key_lookup(_user(UserRole.MAINTAINERS)):
        response = TestClient(app).post("/mcp", headers={"Authorization": "Bearer k"})

    assert (response.status_code, response.text) == (200, "u-1")


@pytest.mark.asyncio
@pytest.mark.unit
async def test_finishing_passes_the_corrections_made_while_sending():
    caller = _caller()
    created = RosterComparisonCreated(id=_RUN_ID, page_url="p", rates=ComparisonRates())
    with patch.object(mcp_router.drafts, "finish_draft", AsyncMock(return_value=created)) as finish:
        await mcp_router.finish_roster_comparison("d", ["row 9: Montpellier to Montpelier"], _ctx(caller))

    finish.assert_awaited_once_with("d", caller.user_id, ["row 9: Montpellier to Montpelier"])


@pytest.mark.asyncio
@pytest.mark.unit
async def test_listing_a_states_jurisdictions_is_the_search_with_no_query_paged():
    result = JurisdictionSearchResult(jurisdiction_ocdid="ocd-jurisdiction/x", level="local", name="Barre")
    with patch.object(mcp_router, "search_in_state", AsyncMock(return_value=(291, [result]))) as search:
        page = await mcp_router.list_jurisdictions("VT", page=2)

    size = mcp_router.LIST_PAGE_SIZE
    search.assert_awaited_once_with("vt", "", size, size)
    assert page["total_items"] == 291
    assert page["data"][0]["name"] == "Barre"
