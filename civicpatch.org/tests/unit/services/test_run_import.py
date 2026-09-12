"""`run_import` — the batch's own status/error, not just whether it crashed.

A jurisdiction failing is not an exception: `_import_jurisdiction` catches its own and reports
it in the result, so `import_rows` returning normally says nothing about whether every
jurisdiction actually succeeded. Only `import_rows`, `write_back` and `changeset_batches` cross
a real boundary (DB, Sheets), so only those are mocked.
"""

from unittest.mock import AsyncMock, patch

import pytest

from core.entry_rows import ImportStatus
from services.sheet_import import JurisdictionResult, run_import

_BATCH_ID = "batch-1"
_USER_ID = "user-1"


def _result(ocdid: str, status: ImportStatus, error: str | None = None) -> JurisdictionResult:
    return JurisdictionResult(jurisdiction_ocdid=ocdid, status=status, error=error)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_every_jurisdiction_succeeding_finishes_clean():
    results = [_result("ocd-a", ImportStatus.IMPORTED)]
    with (
        patch(
            "services.sheet_import.import_rows", new_callable=AsyncMock, return_value=results
        ),
        patch("services.sheet_import.write_back", new_callable=AsyncMock),
        patch("services.sheet_import.changeset_batches.finish", new_callable=AsyncMock) as finish,
    ):
        await run_import(_BATCH_ID, [], _USER_ID)

    finish.assert_awaited_once()
    _, status = finish.await_args.args
    assert status.value == "succeeded"
    assert finish.await_args.kwargs["error"] is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_a_failed_jurisdiction_marks_the_whole_batch_failed():
    """Otherwise a town silently failing to import reads as a `succeeded` batch with nothing
    to say why nobody there was ever imported."""
    results = [
        _result("ocd-a", ImportStatus.IMPORTED),
        _result("ocd-b", ImportStatus.FAILED, error="unknown jurisdiction"),
    ]
    with (
        patch(
            "services.sheet_import.import_rows", new_callable=AsyncMock, return_value=results
        ),
        patch("services.sheet_import.write_back", new_callable=AsyncMock),
        patch("services.sheet_import.changeset_batches.finish", new_callable=AsyncMock) as finish,
    ):
        await run_import(_BATCH_ID, [], _USER_ID)

    _, status = finish.await_args.args
    assert status.value == "failed"
    assert "ocd-b" in finish.await_args.kwargs["error"]
    assert "unknown jurisdiction" in finish.await_args.kwargs["error"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_finish_still_runs_when_import_rows_raises():
    """The lock has to lift either way, or a crash holds the sheet against every future run."""
    with (
        patch(
            "services.sheet_import.import_rows",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ),
        patch("services.sheet_import.write_back", new_callable=AsyncMock) as write_back,
        patch("services.sheet_import.changeset_batches.finish", new_callable=AsyncMock) as finish,
    ):
        await run_import(_BATCH_ID, [], _USER_ID)

    write_back.assert_not_awaited()
    _, status = finish.await_args.args
    assert status.value == "failed"
    assert "boom" in finish.await_args.kwargs["error"]
