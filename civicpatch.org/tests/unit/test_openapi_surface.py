"""The OpenAPI schema (`/docs`) lists only the documented contract: the public routes, plus the
maintainer-only ones agents discover there. A new route fails here until someone decides."""

import pytest

from main import app

DOCUMENTED_ROUTES = {
    ("GET", "/api/v1/jurisdictions"),
    ("GET", "/api/v1/jurisdictions/available"),
    ("GET", "/api/v1/jurisdictions/states"),
    ("GET", "/api/v1/jurisdictions/geojson"),
    ("POST", "/api/v1/jurisdictions/by-ocdids"),
    ("GET", "/api/v1/jurisdictions/search"),
    ("GET", "/api/v1/jurisdictions/activity"),
    ("GET", "/api/v1/jurisdictions/in-flight"),
    ("GET", "/api/v1/jurisdictions/{jurisdiction_ocdid}/roster-source-urls"),
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
    # Maintainers only, but documented: agents discover them here and through MCP.
    ("POST", "/api/v1/roster-comparisons"),
    ("GET", "/api/v1/roster-comparisons"),
    ("POST", "/api/v1/roster-comparisons/drafts"),
    ("POST", "/api/v1/roster-comparisons/drafts/{draft_id}/rows"),
    ("POST", "/api/v1/roster-comparisons/drafts/{draft_id}/finish"),
    ("GET", "/api/v1/roster-comparisons/{run_id}"),
    ("GET", "/api/v1/roster-comparisons/{run_id}/jurisdictions/{jurisdiction_ocdid}"),
    ("GET", "/api/v1/roster-comparisons/{run_id}/jurisdictions"),
    ("GET", "/api/v1/roster-comparisons/{run_id}/report"),
    ("GET", "/api/v1/roster-comparisons/{run_id}/people"),
}


@pytest.mark.unit
def test_openapi_schema_lists_only_documented_routes():
    documented = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    assert documented == DOCUMENTED_ROUTES
