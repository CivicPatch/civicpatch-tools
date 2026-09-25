"""The OpenAPI schema (`/docs`) lists only the public contract. Every other route is
`include_in_schema=False`, so a new route fails here until someone decides whether it is public.
"""

import pytest

from main import app

PUBLIC_ROUTES = {
    ("GET", "/api/v1/jurisdictions"),
    ("GET", "/api/v1/jurisdictions/available"),
    ("GET", "/api/v1/jurisdictions/states"),
    ("GET", "/api/v1/jurisdictions/geojson"),
    ("POST", "/api/v1/jurisdictions/by-ocdids"),
    ("GET", "/api/v1/jurisdictions/search"),
    ("GET", "/api/v1/jurisdictions/history"),
    ("GET", "/api/v1/jurisdictions/in-flight"),
    ("GET", "/api/v1/people"),
    ("GET", "/api/v1/people/geo"),
    ("GET", "/api/v1/memberships/{jurisdiction_ocdid}"),
    ("GET", "/api/v1/organizations/{jurisdiction_ocdid}"),
    ("GET", "/api/v1/roles"),
    ("GET", "/api/v1/change_logs/recent-publications"),
    ("GET", "/api/v1/data/dashboard"),
    ("GET", "/api/v1/leaderboard"),
    ("GET", "/api/v1/coverage"),
    ("GET", "/api/v1/coverage/{state}/local"),
    ("GET", "/api/v1/coverage/{state}/summary"),
    ("GET", "/api/v1/coverage/{state}/municipalities"),
    ("GET", "/api/v1/blog/posts"),
    ("GET", "/api/v1/elections"),
}


@pytest.mark.unit
def test_openapi_schema_lists_only_public_routes():
    documented = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    assert documented == PUBLIC_ROUTES
