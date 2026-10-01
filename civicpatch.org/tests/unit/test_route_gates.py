"""Who gets past each real route's gates, as `main.app` mounts them, router-wide gates included.

Calls only the `require_route_access` dependencies FastAPI would run for a route, never the
handler, so no database is needed. The route tests mount routers bare, without `main.py`'s
router-wide gates, which is how a gate refusing the pipeline's key on every run route got past
them.
"""

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from main import app
from schemas.common import Identity, UserRole

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


async def _passes(route: APIRoute, identity: Identity) -> bool:
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
        ("PUT", "/api/admin/users/{user_id}/role"),
        ("GET", "/api/admin/users"),
        ("POST", "/api/admin/users/{user_id}/rollback"),
    ],
)
async def test_the_service_key_is_refused_by_person_routes(method, path):
    assert not await _passes(_route(method, path), SERVICE_KEY)


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
