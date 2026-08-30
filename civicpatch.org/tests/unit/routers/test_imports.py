"""Thin HTTP-contract tests for the sheet-import endpoints.

What lives here is the contract: which status code each failure maps to, and that the work
happens in a background task rather than in the response. The ingest itself is covered
full-stack in tests/integration/services/test_sheet_import.py — re-testing it through HTTP would
say nothing new and would need five mocks to say it.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from lib.auth import get_optional_user
from services.entry_sheet import SheetNotConfigured
from routers.api import imports as imports_router
from schemas.common import Identity, UserRole
from schemas.imports import ImportPreview
from services.sheet_import import SheetRead

_PREFIX = "/imports"
_EMPTY_PREVIEW = ImportPreview(
    jurisdictions_ready=[],
    jurisdictions_blocked=[],
    rows=0,
    errors=[],
)


def _client(role: UserRole = UserRole.MAINTAINERS) -> TestClient:
    app = FastAPI()
    app.dependency_overrides[get_optional_user] = lambda: Identity(
        type="cookie",
        provider="supabase",
        provider_user_id="user-uuid",
        email="user@example.com",
        role=role.value,
        user_id="00000000-0000-4000-8000-000000000001",
    )
    app.include_router(imports_router.get_router(), prefix=_PREFIX)
    return TestClient(app)


@pytest.mark.unit
def test_an_unconfigured_sheet_is_a_503():
    """There is one curated sheet and it is configured, not chosen — so a missing setting is a
    deployment problem, not something the caller got wrong. docker-compose defaults it in dev."""
    with patch(
        "routers.api.imports.entry_sheet.spreadsheet_id",
        side_effect=SheetNotConfigured("ENTRY_SPREADSHEET_ID is not set."),
    ):
        response = _client().post(_PREFIX)
    assert response.status_code == 503


@pytest.mark.unit
def test_a_sheet_we_cannot_read_says_how_to_fix_it():
    """The realistic failure is a sheet nobody shared with us, and a bare 403 leaves the user
    with nothing to do about it."""
    with (
        patch("routers.api.imports.entry_sheet.spreadsheet_id", return_value="abc"),
        patch(
            "routers.api.imports.sheet_import.read_sheet",
            side_effect=PermissionError("403"),
        ),
    ):
        response = _client().post(_PREFIX)
    assert response.status_code == 502
    assert "Share it with" in response.json()["error"]


@pytest.mark.unit
def test_a_second_import_over_one_sheet_is_a_409():
    """Two runs would race each other's write-back, and the second would report against rows
    the first had already changed."""
    from database.request_batches import BatchAlreadyRunning

    with (
        patch("routers.api.imports.entry_sheet.spreadsheet_id", return_value="abc"),
        patch(
            "routers.api.imports.sheet_import.read_sheet",
            return_value=SheetRead(rows=[], preview=_EMPTY_PREVIEW),
        ),
        patch(
            "routers.api.imports.request_batches.start",
            new_callable=AsyncMock,
            side_effect=BatchAlreadyRunning("sheet:abc"),
        ),
    ):
        response = _client().post(_PREFIX)
    assert response.status_code == 409


@pytest.mark.unit
def test_starting_returns_the_batch_and_defers_the_work():
    """The response carries the preview and an id to poll — the ingest runs after it is sent."""
    with (
        patch("routers.api.imports.entry_sheet.spreadsheet_id", return_value="abc"),
        patch(
            "routers.api.imports.sheet_import.read_sheet",
            return_value=SheetRead(rows=[], preview=_EMPTY_PREVIEW),
        ),
        patch(
            "routers.api.imports.request_batches.start",
            new_callable=AsyncMock,
            return_value="batch-1",
        ),
        patch(
            "routers.api.imports.run_import_task", new_callable=AsyncMock
        ) as task,
    ):
        response = _client().post(_PREFIX)

    assert response.status_code == 200
    assert response.json()["data"]["batch_id"] == "batch-1"
    task.assert_awaited_once()


@pytest.mark.unit
def test_preview_takes_no_lock():
    """It writes nothing and claims nothing, so it is safe to run on every Check."""
    with (
        patch("routers.api.imports.entry_sheet.spreadsheet_id", return_value="abc"),
        patch(
            "routers.api.imports.sheet_import.read_sheet",
            return_value=SheetRead(rows=[], preview=_EMPTY_PREVIEW),
        ),
        patch(
            "routers.api.imports.request_batches.start", new_callable=AsyncMock
        ) as start,
    ):
        response = _client().post(f"{_PREFIX}/preview")

    assert response.status_code == 200
    start.assert_not_awaited()


@pytest.mark.unit
def test_polling_an_unknown_batch_is_a_404():
    with patch(
        "routers.api.imports.request_batches.get",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = _client().get(f"{_PREFIX}/missing")
    assert response.status_code == 404


@pytest.mark.unit
def test_contributors_cannot_start_an_import():
    """Publishing what an import proposes is a maintainer action, and so is raising it."""
    response = _client(UserRole.CONTRIBUTORS).post(_PREFIX)
    assert response.status_code in (401, 403)


@pytest.mark.unit
def test_no_import_ever_run_is_not_an_error():
    """The page asks on every load, and "nothing yet" is the ordinary first answer."""
    with patch(
        "routers.api.imports.request_batches.latest",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = _client().get(f"{_PREFIX}/latest")

    assert response.status_code == 200
    assert response.json()["data"] is None


@pytest.mark.unit
def test_latest_is_not_read_as_a_batch_id():
    """`/latest` is declared before `/{batch_id}`; swapping them would route it into the
    progress lookup and 404."""
    with patch(
        "routers.api.imports.request_batches.get",
        new_callable=AsyncMock,
        return_value=None,
    ) as by_id:
        with patch(
            "routers.api.imports.request_batches.latest",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = _client().get(f"{_PREFIX}/latest")

    assert response.status_code == 200
    by_id.assert_not_awaited()


