"""Who gets past each real route's gates, as `main.app` mounts them, router-wide gates included.

Calls only the `require_route_access` dependencies FastAPI would run for a route, never the
handler, so no database is needed. The route tests mount routers bare, without `main.py`'s
router-wide gates, which is how a gate refusing the pipeline's key on every run route got past
them.
"""

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from lib.auth import get_optional_user
from main import app
from schemas.common import ApiKeyScope, Identity, UserRole

pytestmark = pytest.mark.unit

SERVICE_KEY = Identity(
    type="service_api_key",
    provider="system",
    provider_user_id="service_api_key",
    email="service@civicpatch.org",
)


def _person(role: UserRole) -> Identity:
    return Identity(
        type="cookie",
        provider="supabase",
        provider_user_id=f"sb-{role.value}",
        email=f"{role.value}@example.com",
        role=role.value,
        user_id="00000000-0000-4000-8000-0000000000aa",
    )


# Every route the service key is used for (surveyed 2026-10-01, see the whitelist plan).
KEY_ROUTES = [
    ("GET", "/api/v1/jurisdictions"),
    ("POST", "/api/v1/jurisdictions/by-ocdids"),
    ("GET", "/api/v1/jurisdictions/{jurisdiction_ocdid:path}/roster-source-urls"),
    ("POST", "/api/v1/jurisdictions/{jurisdiction_ocdid:path}/pull_requests"),
    ("PATCH", "/api/v1/jurisdictions/{jurisdiction_ocdid:path}"),
    ("GET", "/api/v1/organizations/{jurisdiction_ocdid:path}"),
    ("GET", "/api/v1/people/search"),
    ("GET", "/api/v1/roles"),
    ("POST", "/api/v1/pipeline_runs/register"),
    ("GET", "/api/v1/pipeline_runs/{pipeline_run_id}/config"),
    ("GET", "/api/v1/pipeline_runs/{pipeline_run_id}/status"),
    ("PATCH", "/api/v1/pipeline_runs/{pipeline_run_id}/status"),
    ("POST", "/api/v1/pipeline_runs/{pipeline_run_id}/submit"),
    ("POST", "/api/v1/pipeline_runs/batch/claim"),
    ("POST", "/api/admin/jurisdiction_configs/sync"),
]

SERVICE_ONLY_ADMIN_ROUTE = ("POST", "/api/admin/jurisdiction_configs/sync")


def _route(method: str, path: str) -> APIRoute:
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route
    raise LookupError(f"{method} {path} is not mounted")


def _gates(dependant) -> list:
    found = []
    for dependency in dependant.dependencies:
        if "require_route_access" in getattr(dependency.call, "__qualname__", ""):
            found.append(dependency.call)
        found.extend(_gates(dependency))
    return found


async def _passes(route: APIRoute, identity: Identity | None) -> bool:
    for gate in _gates(route.dependant):
        try:
            await gate(identity=identity)
        except HTTPException:
            return False
    return True


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", KEY_ROUTES)
async def test_the_service_key_reaches_every_route_it_is_used_for(method, path):
    # Some are ungated (public by having no gate). That the helper finds gates at all is what
    # `test_the_service_key_is_refused_by_person_routes` proves.
    assert await _passes(_route(method, path), SERVICE_KEY)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/api/v1/organizations/{organization_id}/posts"),
        ("PATCH", "/api/v1/posts/{post_id}"),
        ("DELETE", "/api/v1/posts/{post_id}"),
        ("PUT", "/api/admin/users/{user_id}/role"),
        ("GET", "/api/admin/users"),
        ("POST", "/api/admin/users/{user_id}/rollback"),
    ],
)
async def test_the_service_key_is_refused_by_person_routes(method, path):
    assert not await _passes(_route(method, path), SERVICE_KEY)


AGENT_KEY = Identity(
    type="user_key",
    provider="supabase",
    provider_user_id="sb-agent",
    email="agent@example.com",
    role=UserRole.MAINTAINERS.value,
    user_id="00000000-0000-4000-8000-0000000000bb",
    key_scope=ApiKeyScope.AGENT,
)
OAUTH_TOKEN = AGENT_KEY.model_copy(update={"type": "oauth_token"})
# An MCP client signed in through Supabase's OAuth server must reach exactly what an agent key does.
AGENT_CALLERS = pytest.mark.parametrize("caller", [AGENT_KEY, OAUTH_TOKEN], ids=["agent_key", "oauth_token"])

# Every route an agent key reaches beyond the public ones: MCP, and the comparisons (CLI agents
# upload with curl). A route joins by passing `agent_key=AgentKey.ACCEPTED` and being listed here.
AGENT_KEY_ROUTES = {
    ("GET", "/mcp"),
    ("POST", "/mcp"),
    ("DELETE", "/mcp"),
    ("POST", "/api/v1/roster-comparisons"),
    ("GET", "/api/v1/roster-comparisons"),
    ("POST", "/api/v1/roster-comparisons/drafts"),
    ("POST", "/api/v1/roster-comparisons/drafts/{draft_id}/rows"),
    ("POST", "/api/v1/roster-comparisons/drafts/{draft_id}/finish"),
    ("GET", "/api/v1/roster-comparisons/{run_id}"),
    ("GET", "/api/v1/roster-comparisons/{run_id}/jurisdictions/{jurisdiction_ocdid:path}"),
    ("GET", "/api/v1/roster-comparisons/{run_id}/jurisdictions"),
    ("GET", "/api/v1/roster-comparisons/{run_id}/people"),
}


@pytest.mark.asyncio
@AGENT_CALLERS
async def test_an_agent_caller_reaches_exactly_its_routes_beyond_the_public_ones(caller):
    beyond_public = {
        key
        for route in app.routes
        if isinstance(route, APIRoute)
        and await _passes(route, caller)
        and not await _passes(route, None)
        for key in _route_keys(route)
    }
    assert beyond_public == AGENT_KEY_ROUTES


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [
        ("PATCH", "/api/v1/jurisdictions/{jurisdiction_ocdid:path}"),
        ("POST", "/api/v1/organizations/{organization_id}/posts"),
        ("POST", "/api/v1/api_keys"),
        ("POST", "/api/v1/api_keys/{api_key_id}/revoke"),
    ],
)
@AGENT_CALLERS
async def test_an_agent_caller_is_refused_by_writes_its_owner_may_make(method, path, caller):
    """Its owner is a maintainer: these are what a leaked agent key or token must not reach."""
    route = _route(method, path)
    assert await _passes(route, _person(UserRole.MAINTAINERS))
    assert not await _passes(route, caller)


# challenge_unidentified (/mcp) reads only whether there is a caller, never its role.
RAW_CALLER_READERS = ("require_route_access", "get_optional_person", "challenge_unidentified")


def _direct_caller_reads(dependant, parent=None) -> list[str]:
    found = []
    for dependency in dependant.dependencies:
        if dependency.call is get_optional_user and parent not in RAW_CALLER_READERS:
            found.append(parent or "the route")
        name = getattr(dependency.call, "__qualname__", "").split(".")[0]
        found.extend(_direct_caller_reads(dependency, name))
    return found


def test_only_the_gate_and_its_named_readers_read_the_raw_caller():
    """Anything else would hand an agent key its owner's role outside the routes that opt in."""
    leaks = [
        f"{sorted(route.methods)} {route.path} via {where}"
        for route in app.routes
        if isinstance(route, APIRoute)
        for where in _direct_caller_reads(route.dependant)
    ]
    assert leaks == []


@pytest.mark.asyncio
async def test_every_admin_route_but_sync_refuses_a_non_admin():
    """The admin router has no router-wide gate, so each route must carry its own."""
    admin_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/admin/")
    ]
    assert admin_routes
    maintainer = _person(UserRole.MAINTAINERS)
    for route in admin_routes:
        if (next(iter(route.methods)), route.path) == SERVICE_ONLY_ADMIN_ROUTE:
            continue
        assert not await _passes(route, maintainer), f"{route.methods} {route.path}"
        assert await _passes(route, _person(UserRole.ADMINS)), f"{route.methods} {route.path}"


# ── every route is gated, or deliberately open ───────────────────────────────
# Every route of every type, Starlette routes and mounts included: they cannot carry the gate.

_DOCS = "FastAPI's docs: lists only the public contract (test_openapi_surface)"

DELIBERATELY_OPEN: dict[tuple[str, str], str] = {
    ("GET", "/"): "home page, public",
    ("GET", "/activity"): "redirect to /activity/all-activity, which is gated",
    ("GET", "/api/permissions"): "the caller's own permission flags, all false when signed out",
    ("GET", "/api/v1/me"): "the caller's own identity, or none",
    ("GET", "/api/v1/change_logs/recent-publications"): "public per README",
    ("GET", "/api/v1/memberships/{jurisdiction_ocdid:path}"): "public per README",
    ("GET", "/api/v1/organizations/{jurisdiction_ocdid:path}"): "public per README",
    ("GET", "/api/v1/roles"): "public per README",
    ("GET", "/blog"): "public",
    ("GET", "/blog/{slug}"): "public",
    ("GET", "/login"): "sign-in page",
    ("GET", "/login/username"): "a signed-in user picks a username here; the handler sends the signed-out to /login",
    ("GET", "/{path:path}"): "jurisdiction page, public",
    ("GET", "/{path:path}/activity"): "a jurisdiction's activity, public like its page; the scrape-pages panel inside is maintainers'",
    ("GET", "/{state}/counties"): "public",
    ("GET", "/{state}/municipalities"): "public",
    ("GET", "/docs"): _DOCS,
    ("HEAD", "/docs"): _DOCS,
    ("GET", "/docs/oauth2-redirect"): _DOCS,
    ("HEAD", "/docs/oauth2-redirect"): _DOCS,
    ("GET", "/openapi.json"): _DOCS,
    ("HEAD", "/openapi.json"): _DOCS,
    ("GET", "/redoc"): _DOCS,
    ("HEAD", "/redoc"): _DOCS,
    ("POST", "/webhooks/blog-sync"): "HMAC-verified inside the handler",
    ("POST", "/webhooks/github"): "HMAC-verified inside the handler",
    ("*", "/ws"): "websocket; authenticates through get_ws_user",
    ("*", "/frontend"): "static assets (the built frontend)",
}
# Pages redirect to / instead of refusing, through their own gate.
# A page that redirects the signed-out (require_page_auth) or the unpermitted (require_page_permission).
PAGE_GATES = ("require_page_permission", "require_page_auth")


def _gated(route) -> bool:
    if not isinstance(route, APIRoute):
        return False
    return bool(_gates(route.dependant)) or any(_has_dependency(route.dependant, gate) for gate in PAGE_GATES)


def _has_dependency(dependant, name: str) -> bool:
    return any(
        name in getattr(dependency.call, "__qualname__", "") or _has_dependency(dependency, name)
        for dependency in dependant.dependencies
    )


def _route_keys(route) -> list[tuple[str, str]]:
    methods = sorted(getattr(route, "methods", None) or {"*"})
    return [(method, getattr(route, "path", repr(route))) for method in methods]


def test_every_route_is_gated_or_deliberately_open():
    ungated = sorted(
        key
        for route in app.routes
        if not _gated(route)
        for key in _route_keys(route)
        if key not in DELIBERATELY_OPEN
    )
    assert ungated == [], "\n".join(f"{method} {path}" for method, path in ungated)
