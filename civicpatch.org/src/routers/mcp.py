"""civicpatch as a remote MCP server at `/mcp`: read-only tools, each calling the same function
as its `/api/v1/` route. Uploading is `curl`, not a tool, so the rows never pass through the chat."""

from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request, Response
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.types import ASGIApp, Receive, Scope, Send

import services.roster_comparison as roster_comparisons
import services.roster_comparison_drafts as drafts
from lib.auth import require_route_access
from routers.api.jurisdictions import search_in_state
from routers.api.people import current_roster
from schemas.common import Identity, RouteCategory, UserRole
from schemas.roster_comparisons import (
    MAX_ROWS_PER_BATCH,
    ComparedField,
    DraftRows,
    FieldFilter,
    RosterComparisonHeader,
    UploadedRow,
)

MCP_PATH = "/mcp"
CALLER_STATE = "civicpatch_caller"
SEARCH_LIMIT = 10
FIELD_PAGE_LIMIT = 200
RUN_PAGE_LIMIT = 100

INSTRUCTIONS = """\
civicpatch keeps rosters of local elected officials. These tools read them, and read roster
comparisons: a user's own list of officials compared with civicpatch's.

To compare a user's file (usually one state's officials):
1. Read the header and a few rows only. Never read every row into the conversation.
2. Write a script that converts every row into the JSON body of POST /api/v1/roster-comparisons
   (its schema is in {instance_url}/openapi.json): state, source_columns, corrections, rows. Each row needs
   source_row (its row number in the original file), jurisdiction_ocdid and name; role, emails,
   phones, urls and start_date when the file has them. Any other column goes in as is.
3. Correct only jurisdiction_ocdid and name, and only when obviously wrong: "Smith, Bob" to
   "Bob Smith"; "Mayor Bob Smith" to "Bob Smith"; a town name to its ocdid (find_jurisdiction).
   Leave every other value exactly as the file has it, even if it looks wrong: the comparison
   is measuring the user's data. List what you changed, and rows you could not place, in
   corrections, citing row numbers. Send an empty list if you changed nothing.
4. Send it one of two ways, whichever works where you run:
   a. Your shell has CIVICPATCH_API_KEY and can reach {instance_url}: run the script, then
        curl -sS -X POST "{instance_url}/api/v1/roster-comparisons" \\
          -H "Authorization: Bearer $CIVICPATCH_API_KEY" -H "Content-Type: application/json" \\
          --data-binary @comparison.json
      Never print, echo or ask the user for the key: use the variable.
   b. Otherwise (no key in the shell, or the network is blocked, as in a browser chat's
      sandbox): start_roster_comparison with state, source_columns and corrections, then
      add_roster_comparison_rows in batches of up to {batch} rows, then finish_roster_comparison.
      This sends every row through the conversation, so use it only when (a) cannot work.
      Never ask the user for the key instead.
5. The response gives the run's id, its page_url and its rates. End your reply with the page_url
   on a line of its own, then read the run with get_roster_comparison and the jurisdictions they
   ask about.
"""


def build_server(instance_url: str) -> MCPServer:
    instructions = INSTRUCTIONS.replace("{instance_url}", instance_url.rstrip("/")).replace(
        "{batch}", str(MAX_ROWS_PER_BATCH)
    )
    server = MCPServer(name="civicpatch", instructions=instructions)
    server.add_tool(find_jurisdiction, description="A state's jurisdictions whose name matches, with their ocdids.")
    server.add_tool(get_jurisdiction_people, description="A jurisdiction's current officials (open memberships) and its civicpatch page.")
    server.add_tool(list_roster_comparisons, description="Saved comparisons, newest first, each with its page_url.")
    server.add_tool(get_roster_comparison, description="A saved comparison: state rates, then jurisdictions, most unmatched first.")
    server.add_tool(get_roster_comparison_jurisdiction, description="One jurisdiction's people in a saved comparison.")
    server.add_tool(
        get_roster_comparison_field,
        description="The matched people behind a field's conflict or one_side_has_more count, paged.",
    )
    server.add_tool(
        start_roster_comparison,
        description="Start an upload sent in batches (when curl cannot reach civicpatch): state, source_columns, corrections. Returns a draft id.",
    )
    server.add_tool(
        add_roster_comparison_rows,
        description=f"Add up to {MAX_ROWS_PER_BATCH} converted rows to a draft. Call again for the next batch.",
    )
    server.add_tool(
        finish_roster_comparison,
        description="Compare a draft's rows with civicpatch and keep the run. Returns its id, page_url and rates.",
    )
    return server


async def find_jurisdiction(state: str, name: str) -> list[dict]:
    """`state` is the two-letter code, lowercase."""
    _, results = await search_in_state(state.lower(), name, SEARCH_LIMIT, 0)
    return [result.model_dump(mode="json") for result in results]


async def get_jurisdiction_people(jurisdiction_ocdid: str) -> dict:
    people = await current_roster(jurisdiction_ocdid)
    return {"page_url": people["page_url"], "data": [p.model_dump(mode="json") for p in people["data"]]}


async def list_roster_comparisons(page: int = 1, per_page: int = 20) -> dict:
    page_of_runs = await roster_comparisons.list_runs(max(page, 1), max(1, min(per_page, RUN_PAGE_LIMIT)))
    return page_of_runs.model_dump(mode="json")


async def get_roster_comparison(run_id: str) -> dict:
    return (await roster_comparisons.get_run_summary(run_id)).model_dump(mode="json")


async def get_roster_comparison_jurisdiction(run_id: str, jurisdiction_ocdid: str) -> list[dict]:
    people = await roster_comparisons.get_run_people(run_id, jurisdiction_ocdid)
    return [person.model_dump(mode="json") for person in people]


async def get_roster_comparison_field(
    run_id: str, field: ComparedField, level: FieldFilter, page: int = 1, per_page: int = 50
) -> dict:
    page_of_people = await roster_comparisons.get_run_field_page(
        run_id, field, level, max(page, 1), max(1, min(per_page, FIELD_PAGE_LIMIT))
    )
    return page_of_people.model_dump(mode="json")


def caller_id(ctx: Context) -> str:
    """The user the `/mcp` gate let in, as the route left them on the request."""
    request = ctx.request_context.request
    identity = getattr(getattr(request, "state", None), CALLER_STATE, None)
    if identity is None or not identity.user_id:
        raise PermissionError("No signed-in user on this request.")
    return identity.user_id


async def start_roster_comparison(
    state: str, source_columns: dict[str, list[str]], corrections: list[str], ctx: Context
) -> dict:
    header = RosterComparisonHeader(state=state, source_columns=source_columns, corrections=corrections)
    return (await drafts.start_draft(header, caller_id(ctx))).model_dump(mode="json")


async def add_roster_comparison_rows(draft_id: str, rows: list[UploadedRow], ctx: Context) -> dict:
    batch = DraftRows(rows=rows)
    return (await drafts.add_draft_rows(draft_id, batch.rows, caller_id(ctx))).model_dump(mode="json")


async def finish_roster_comparison(draft_id: str, ctx: Context) -> dict:
    return (await drafts.finish_draft(draft_id, caller_id(ctx))).model_dump(mode="json")


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


def get_router(mcp_app: ASGIApp) -> APIRouter:
    """A FastAPI route, so `/mcp` is gated by `require_route_access` like every other route."""
    router = APIRouter()

    @router.api_route(MCP_PATH, methods=["GET", "POST", "DELETE"], include_in_schema=False)
    async def mcp_endpoint(
        request: Request,
        identity: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)),
    ) -> Response:
        # The tools read the caller from here: the gate has already checked them.
        setattr(request.state, CALLER_STATE, identity)
        return ForwardToMcp(mcp_app)

    return router
