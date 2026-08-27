"""Starting and watching a curated-sheet import.

`/api/internal/` because the response is UI-shaped and the frontend is the sole consumer.
"""

import logging

from database import request_batches
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from lib.auth import require_route_access
from schemas.common import Identity, RouteCategory, UserRole
from schemas.imports import ImportProgress, StartImportResponse
from services import entry_sheet, sheet_import

logger = logging.getLogger(__name__)


async def run_import_task(
    batch_id: str, rows: list, ready: set, user_id: str
) -> None:
    """Module level per the background-task convention: importable, no closed-over state."""
    await sheet_import.run_import(batch_id, rows, ready, user_id)


def get_router() -> APIRouter:
    router = APIRouter()

    @router.post("/preview")
    async def preview_import_endpoint(
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """What an import would do. Reads the sheet, writes nothing, takes no lock."""
        try:
            read = await sheet_import.read_sheet(entry_sheet.spreadsheet_id())
        except entry_sheet.SheetNotConfigured as e:
            return JSONResponse({"error": str(e)}, status_code=503)
        except Exception as e:
            return JSONResponse({"error": _sharing_hint(e)}, status_code=502)
        return {"data": read.preview}

    @router.post("")
    async def start_import_endpoint(
        background_tasks: BackgroundTasks,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """Claim the lock, then ingest in the background.

        The sheet is read here, not in the task, so an unreachable sheet fails while the user is
        still looking at it rather than as a batch that starts and dies.
        """
        if not user.user_id:
            return JSONResponse({"error": "User ID not available"}, status_code=401)
        try:
            spreadsheet_id = entry_sheet.spreadsheet_id()
            read = await sheet_import.read_sheet(spreadsheet_id)
        except entry_sheet.SheetNotConfigured as e:
            return JSONResponse({"error": str(e)}, status_code=503)
        except Exception as e:
            return JSONResponse({"error": _sharing_hint(e)}, status_code=502)

        try:
            batch_id = await request_batches.start(
                request_batches.BatchKind.SHEET_IMPORT,
                f"sheet:{spreadsheet_id}",
                user.user_id,
                {"spreadsheet_id": spreadsheet_id},
                items_total=len(read.ready),
            )
        except request_batches.BatchAlreadyRunning as e:
            # Not queued: two runs would race each other's write-back.
            return JSONResponse({"error": str(e)}, status_code=409)

        background_tasks.add_task(
            run_import_task, batch_id, read.rows, read.ready, user.user_id
        )
        return {"data": StartImportResponse(batch_id=batch_id, preview=read.preview)}

    @router.get("/{batch_id}")
    async def import_progress_endpoint(
        batch_id: str,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        batch = await request_batches.get(batch_id)
        if batch is None:
            return JSONResponse({"error": "No such import."}, status_code=404)
        return {
            "data": ImportProgress(
                batch_id=batch["id"],
                status=batch["status"],
                items_total=batch["items_total"],
                items_done=batch["items_done"],
                error=batch["error"],
                started_at=batch["started_at"].isoformat(),
                finished_at=batch["finished_at"].isoformat()
                if batch["finished_at"]
                else None,
            )
        }

    @router.delete("/{batch_id}")
    async def release_import_endpoint(
        batch_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, UserRole.MAINTAINERS)
        ),
    ):
        """Clear a batch that is not coming back, freeing its lock. Manual on purpose."""
        if not user.user_id:
            return JSONResponse({"error": "User ID not available"}, status_code=401)
        batch = await request_batches.get(batch_id)
        if batch is None:
            return JSONResponse({"error": "No such import."}, status_code=404)
        released = await request_batches.release(batch["lock_key"], user.user_id)
        return {"data": {"released": released}}

    return router


def _sharing_hint(error: Exception) -> str:
    """The realistic failure is a sheet nobody shared with us; a bare 403 is unactionable."""
    logger.warning(f"Could not read spreadsheet: {error}")
    return (
        "Could not read that sheet. Share it with the civicpatch service account as an "
        "Editor, then try again."
    )
