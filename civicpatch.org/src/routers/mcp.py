"""civicpatch as a remote MCP server at `/mcp`: read-only tools, each calling the same function
as its `/api/v1/` route. Uploading is `curl`, not a tool, so the rows never pass through the chat."""

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import ValidationError
from starlette.types import ASGIApp, Receive, Scope, Send

import services.roster_comparison as roster_comparisons
import services.roster_comparison_drafts as drafts
import environment
from lib.auth import API_COOKIE, API_HEADER, get_optional_user, require_route_access
from lib.supabase_tokens import fetch_authorization_server_metadata, fetch_issuer
from routers.api.jurisdictions import MAX_SEARCH_LIMIT, search_in_state
from routers.api.people import current_roster
from schemas.common import AgentKey, Identity, RouteCategory, UserRole
from schemas.pagination import paginated_response, pagination_offset
from schemas.roster_comparisons import (
    MAX_ROWS_PER_BATCH,
    ComparedField,
    DraftFinish,
    DraftRows,
    FieldFilter,
    PeopleFilter,
    PersonOutcome,
    RosterComparisonHeader,
    UploadedRow,
)

MCP_PATH = "/mcp"
PROTECTED_RESOURCE_PATH = "/.well-known/oauth-protected-resource"
# ChatGPT looks for the authorization server's document on the MCP server's own origin, whatever the
# protected resource names; each path serves Supabase's, unchanged.
AUTHORIZATION_SERVER_PATHS = [
    "/.well-known/oauth-authorization-server",
    f"/.well-known/oauth-authorization-server{MCP_PATH}",
    f"{MCP_PATH}/.well-known/oauth-authorization-server",
    "/.well-known/openid-configuration",
    f"/.well-known/openid-configuration{MCP_PATH}",
    f"{MCP_PATH}/.well-known/openid-configuration",
]
CALLER_STATE = "civicpatch_caller"
SEARCH_LIMIT = 10
LIST_PAGE_SIZE = MAX_SEARCH_LIMIT
PEOPLE_PAGE_LIMIT = 200
RUN_PAGE_LIMIT = 100
# Raised as a ToolError so the agent reads why; the SDK hides any other exception's message.
AGENT_REFUSALS = (
    ValidationError,
    roster_comparisons.RunNotFound,
    roster_comparisons.RowsOutsideState,
    drafts.DraftNotFound,
    drafts.DraftTooLarge,
    drafts.DraftIsEmpty,
)

INSTRUCTIONS = """\
civicpatch keeps rosters of local elected officials. These tools read them, and run and read
roster comparisons: a user's own list of officials compared with civicpatch's.

To compare a user's file (usually one state's officials):
1. Read the header and a few rows only. Never read every row into the conversation.
2. Write a script that converts every row into the JSON body of POST /api/v1/roster-comparisons
   (its schema is in {instance_url}/openapi.json): state, source_columns, corrections, rows. Each row needs
   source_row (its row number in the original file), jurisdiction_ocdid and name; role, emails,
   phones, urls and start_date when the file has them. Any other column goes in as is.
3. Never write an ocdid yourself. Get the state's local jurisdictions and map each row's
   jurisdiction (town, city, village) to its jurisdiction_ocdid. The list is one search, reachable two ways. If your script can reach
   {instance_url}, have it call
   GET {instance_url}/api/v1/jurisdictions/search?state=<state>&limit={page_size}&page=N
   (public, no key needed; the names never enter the conversation). Otherwise use the
   list_jurisdictions tool, page by page. Search the names that do not match (find_jurisdiction,
   or the same URL with &q=<name>). Tell the user which rows did not match and what you matched
   each to, and ask them about any that search cannot settle (two candidates, or none) before
   sending. A row you cannot place cannot be sent: leave it out only if the user agrees.
4. Correct names only when obviously wrong: "Smith, Bob" to "Bob Smith"; "Mayor Bob Smith" to
   "Bob Smith". Leave every other value exactly as the file has it, even if it looks wrong: the
   comparison is measuring the user's data. List in corrections, citing row numbers, every
   jurisdiction you matched by search, every name you changed, and every row the user agreed to
   leave out. Send an empty list if you changed nothing.
5. Send it one of two ways, whichever works where you run:
   a. Your shell has CIVICPATCH_API_KEY and can reach {instance_url}: run the script, then
        curl -sS -X POST "{instance_url}/api/v1/roster-comparisons" \\
          -H "Authorization: Bearer $CIVICPATCH_API_KEY" -H "Content-Type: application/json" \\
          --data-binary @comparison.json
      Never print, echo or ask the user for the key: use the variable.
   b. Otherwise (no key in the shell, or the network is blocked, as in a browser chat's
      sandbox): start_roster_comparison with state and source_columns, then
      add_roster_comparison_rows in batches of up to {batch} rows, then finish_roster_comparison
      with corrections.
      This sends every row through the conversation, so use it only when (a) cannot work.
      Never ask the user for the key instead.
6. A refusal naming rows (HTTP 422 from curl, an error from a tool) means some
   jurisdiction_ocdid is not in the state. Nothing was saved: the whole upload, or with batches
   only that batch (earlier batches stay). Fix those rows as in step 3, tell the user which rows
   failed and what you changed each to, then send again, with those fixes in corrections.
7. The response gives the run's id, its page_url and its rates. End your reply with the page_url
   on a line of its own, then read the run with get_roster_comparison, any jurisdiction the user
   asks about with get_roster_comparison_jurisdiction, and everyone with one outcome across the
   state (e.g. everyone only in the user's file) with get_roster_comparison_people. The state's
   jurisdictions the file has no row for are not compared: count in jurisdictions_not_named,
   names with list_roster_comparison_jurisdictions(compared=false). A jurisdiction whose matched,
   possible_match, only_in_civicpatch and only_in_civicpatch_not_compared are all 0 has no one in
   civicpatch yet: say so, rather than that the user's data disagrees.
8. Counts compare only some organizations (compared_organizations): by default every one the
   user's file matched someone in; civicpatch's other people are only_in_civicpatch_not_compared,
   outside the score. Report which were compared. If the user says their file covers others, or
   fewer, pass organizations to each read tool.
"""


def build_server(instance_url: str) -> MCPServer:
    instructions = INSTRUCTIONS.replace("{instance_url}", instance_url.rstrip("/")).replace(
        "{batch}", str(MAX_ROWS_PER_BATCH)
    ).replace("{page_size}", str(LIST_PAGE_SIZE))
    server = MCPServer(name="civicpatch", instructions=instructions)
    server.add_tool(
        find_jurisdiction,
        description=f"Up to {SEARCH_LIMIT} local jurisdictions in a state whose name is closest, with their ocdids.",
    )
    server.add_tool(
        list_jurisdictions,
        description=f"Every local jurisdiction in a state with its ocdid, ordered by ocdid, {LIST_PAGE_SIZE} a page.",
    )
    server.add_tool(get_jurisdiction_people, description="A jurisdiction's current officials (open memberships) and its civicpatch page.")
    server.add_tool(list_roster_comparisons, description="Saved comparisons, newest first, each with its page_url.")
    server.add_tool(
        get_roster_comparison,
        description=(
            "A saved comparison: state rates, then jurisdictions, most unmatched first, then the organizations "
            "of civicpatch's people with their matched counts. Counts compare compared_organizations only."
        ),
    )
    server.add_tool(get_roster_comparison_jurisdiction, description="One jurisdiction's compared people in a saved comparison.")
    server.add_tool(
        list_roster_comparison_jurisdictions,
        description="A saved comparison's jurisdictions and its state's others (not compared), by name.",
    )
    server.add_tool(
        get_roster_comparison_people,
        description=(
            "A saved comparison's people across every jurisdiction, paged: those with one outcome "
            "(e.g. only_in_uploaded_data), or the matched people behind a field's conflict or "
            "one_side_has_more count (field and level together)."
        ),
    )
    server.add_tool(
        start_roster_comparison,
        description="Start an upload sent in batches (when curl cannot reach civicpatch): state and source_columns. Returns a draft id.",
    )
    server.add_tool(
        add_roster_comparison_rows,
        description=(
            f"Add up to {MAX_ROWS_PER_BATCH} converted rows to a draft. Call again for the next batch. "
            "Safe to resend a batch: a row identical to one already in the draft replaces it."
        ),
    )
    server.add_tool(
        finish_roster_comparison,
        description=(
            "Compare a draft's rows with civicpatch and keep the run. Returns its id, page_url and rates. "
            "corrections: everything you changed, citing row numbers."
        ),
    )
    return server


async def find_jurisdiction(state: str, name: str) -> list[dict]:
    """`state` is the two-letter code, lowercase."""
    _, results = await search_in_state(state.lower(), name, SEARCH_LIMIT, 0)
    return [result.model_dump(mode="json") for result in results]


async def list_jurisdictions(state: str, page: int = 1) -> dict:
    """The same as GET /api/v1/jurisdictions/search with a state and no query."""
    page = max(page, 1)
    total, results = await search_in_state(state.lower(), "", LIST_PAGE_SIZE, pagination_offset(page, LIST_PAGE_SIZE))
    return paginated_response(total, page, LIST_PAGE_SIZE, [result.model_dump(mode="json") for result in results])


async def get_jurisdiction_people(jurisdiction_ocdid: str) -> dict:
    people = await current_roster(jurisdiction_ocdid)
    return {"page_url": people["page_url"], "data": [p.model_dump(mode="json") for p in people["data"]]}


async def list_roster_comparisons(page: int = 1, per_page: int = 20) -> dict:
    page_of_runs = await roster_comparisons.list_runs(max(page, 1), max(1, min(per_page, RUN_PAGE_LIMIT)))
    return page_of_runs.model_dump(mode="json")


async def get_roster_comparison(run_id: str, organizations: list[str] | None = None) -> dict:
    """`organizations`: the ones to compare; left out, every one with a match."""
    try:
        return (await roster_comparisons.get_run_summary(run_id, organizations)).model_dump(mode="json")
    except AGENT_REFUSALS as error:
        raise ToolError(str(error)) from error


async def list_roster_comparison_jurisdictions(run_id: str, compared: bool | None = None) -> list[dict]:
    """`compared`: true for those the uploaded data has rows for, false for the state's others."""
    try:
        jurisdictions = await roster_comparisons.get_run_jurisdictions(run_id, compared)
    except AGENT_REFUSALS as error:
        raise ToolError(str(error)) from error
    return [jurisdiction.model_dump(mode="json") for jurisdiction in jurisdictions]


async def get_roster_comparison_jurisdiction(
    run_id: str, jurisdiction_ocdid: str, organizations: list[str] | None = None
) -> list[dict]:
    try:
        people = await roster_comparisons.get_run_people(run_id, jurisdiction_ocdid, organizations)
    except AGENT_REFUSALS as error:
        raise ToolError(str(error)) from error
    return [person.model_dump(mode="json") for person in people]


async def get_roster_comparison_people(
    run_id: str,
    outcome: PersonOutcome | None = None,
    field: ComparedField | None = None,
    level: FieldFilter | None = None,
    organizations: list[str] | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    try:
        people_filter = PeopleFilter(outcome=outcome, field=field, level=level)
        page_of_people = await roster_comparisons.get_run_people_page(
            run_id, people_filter, organizations, max(page, 1), max(1, min(per_page, PEOPLE_PAGE_LIMIT))
        )
    except AGENT_REFUSALS as error:
        raise ToolError(str(error)) from error
    return page_of_people.model_dump(mode="json")


def caller_id(ctx: Context) -> str:
    """The user the `/mcp` gate let in, as the route left them on the request."""
    request = ctx.request_context.request
    identity = getattr(getattr(request, "state", None), CALLER_STATE, None)
    if identity is None or not identity.user_id:
        raise PermissionError("No signed-in user on this request.")
    return identity.user_id


async def start_roster_comparison(state: str, source_columns: dict[str, list[str]], ctx: Context) -> dict:
    try:
        header = RosterComparisonHeader(state=state, source_columns=source_columns)
        return (await drafts.start_draft(header, caller_id(ctx))).model_dump(mode="json")
    except AGENT_REFUSALS as error:
        raise ToolError(str(error)) from error


async def add_roster_comparison_rows(draft_id: str, rows: list[UploadedRow], ctx: Context) -> dict:
    try:
        batch = DraftRows(rows=rows)
        return (await drafts.add_draft_rows(draft_id, batch.rows, caller_id(ctx))).model_dump(mode="json")
    except AGENT_REFUSALS as error:
        raise ToolError(str(error)) from error


async def finish_roster_comparison(draft_id: str, corrections: list[str], ctx: Context) -> dict:
    try:
        finish = DraftFinish(corrections=corrections)
        return (await drafts.finish_draft(draft_id, caller_id(ctx), finish.corrections)).model_dump(mode="json")
    except AGENT_REFUSALS as error:
        raise ToolError(str(error)) from error


def allowed_hosts(instance_url: str, extra_hosts: list[str]) -> list[str]:
    """The SDK refuses any other Host header (DNS-rebinding guard): ours, local dev, and any
    configured extras (a dev tunnel)."""
    return [urlparse(instance_url).netloc, "localhost:*", "127.0.0.1:*", *extra_hosts]


def build_asgi_app(server: MCPServer, instance_url: str, extra_hosts: list[str]) -> ASGIApp:
    return server.streamable_http_app(
        streamable_http_path=MCP_PATH,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            allowed_hosts=allowed_hosts(instance_url, extra_hosts)
        ),
    )


class ForwardToMcp(Response):
    """Hands the request, untouched, to the MCP app once the route's gate has passed."""

    def __init__(self, mcp_app: ASGIApp):
        super().__init__()
        self.mcp_app = mcp_app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.mcp_app(scope, receive, send)


def public_origin(request: Request) -> str:
    """The address the client used; behind a tunnel or proxy, from its forwarded headers."""
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{scheme}://{host}"


async def challenge_unidentified(
    request: Request,
    identity: Identity | None = Depends(get_optional_user),
    authorization: str | None = Security(API_HEADER),
    cookie: str | None = Security(API_COOKIE),
) -> None:
    """A request with no caller is told where to sign in (RFC 9728); a refused credential is also told it
    is invalid (RFC 6750), which makes an OAuth client refresh an expired token."""
    if identity is not None:
        return
    metadata = f'resource_metadata="{public_origin(request)}{PROTECTED_RESOURCE_PATH}"'
    challenge = f'Bearer error="invalid_token", {metadata}' if authorization or cookie else f"Bearer {metadata}"
    raise HTTPException(
        status_code=401,
        detail="Sign in, or send an API key",
        headers={"WWW-Authenticate": challenge},
    )


def get_router(mcp_app: ASGIApp) -> APIRouter:
    """A FastAPI route, so `/mcp` is gated by `require_route_access` like every other route."""
    router = APIRouter()

    @router.get(PROTECTED_RESOURCE_PATH, include_in_schema=False)
    @router.get(f"{PROTECTED_RESOURCE_PATH}{MCP_PATH}", include_in_schema=False)
    async def protected_resource_endpoint(
        request: Request, _: Identity | None = Depends(require_route_access(RouteCategory.PUBLIC))
    ) -> dict:
        """Where an MCP client signs in: Supabase's OAuth server, whose tokens /mcp accepts."""
        supabase_url = environment.supabase_url()
        return {
            "resource": f"{public_origin(request)}{MCP_PATH}",
            "authorization_servers": [await fetch_issuer(supabase_url)],
            "bearer_methods_supported": ["header"],
        }

    async def authorization_server_endpoint(
        _: Identity | None = Depends(require_route_access(RouteCategory.PUBLIC)),
    ) -> dict:
        """Supabase's OAuth discovery document, for clients that look for it here."""
        return await fetch_authorization_server_metadata(environment.supabase_url())

    for path in AUTHORIZATION_SERVER_PATHS:
        router.add_api_route(path, authorization_server_endpoint, methods=["GET"], include_in_schema=False)

    @router.api_route(MCP_PATH, methods=["GET", "POST", "DELETE"], include_in_schema=False)
    async def mcp_endpoint(
        request: Request,
        _: None = Depends(challenge_unidentified),
        identity: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS, agent_key=AgentKey.ACCEPTED)
        ),
    ) -> Response:
        # The tools read the caller from here: the gate has already checked them.
        setattr(request.state, CALLER_STATE, identity)
        return ForwardToMcp(mcp_app)

    return router
