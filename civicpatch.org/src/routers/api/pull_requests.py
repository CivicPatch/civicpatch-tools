import asyncio
import json
import logging
import os
from typing import List
from shared.schemas import Official
import shared.utils.data_path_utils
import shared.utils.id_utils
import shared.utils.url_utils
from shared.utils.statuses import PullRequestStatus
import yaml
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import database.pipeline_runs
import database.people
import database.pull_requests as pull_requests_db
import database.review_sessions as review_sessions_db
import database.users
import lib.github.api as github_service
import core.pull_request_merge as merge_service
import core.pull_request_sync as pr_sync_service
import lib.redis as redis_store
import lib.storage as storage_service
from database.people import DEFAULT_VIEW, VIEWS
from schemas.common import Identity, Role, RouteCategory
from lib.auth import require_route_access

logger = logging.getLogger(__name__)


def _source_url_to_markdown_url(request_id: str, jurisdiction_ocdid_folder: str, source_url: str) -> str:
    source_url_dir = shared.utils.url_utils.format_url_to_folder(source_url)
    relative_path = os.path.join(request_id, "data_source", jurisdiction_ocdid_folder, "cache", source_url_dir, "preprocessed.md")
    return storage_service.get_civicpatch_artifacts_url(relative_path)


def build_sources(request_id: str, jurisdiction_ocdid: str, source_urls: list[str]) -> list[dict]:
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    return [{"url": url, "markdown": _source_url_to_markdown_url(request_id, folder, url)} for url in source_urls]

# ──────────────────────────────────────────────
# Request models
# ──────────────────────────────────────────────


class PostJobPullRequestDataRequest(BaseModel):
    jurisdiction_ocdid: str
    request_id: str
    data: List[Official]


class SaveAndMergeRequest(BaseModel):
    request_id: str
    jurisdiction_ocdid: str
    data: List[Official] | None = None


# ──────────────────────────────────────────────
# Response models
# ──────────────────────────────────────────────


class DeleteJobResponse(BaseModel):
    request_id: str
    status: str


class ErrorResponse(BaseModel):
    error: str


# ──────────────────────────────────────────────
# Router
# ──────────────────────────────────────────────


def get_router(api_key_header):
    router = APIRouter()

    # -- Pull Requests: List Open Pull Requests ───────────
    # Note: Used by jurisdiction detail page
    # So that's why this isn't paged. Expect max of 1 pull request
    @router.get(
        "",
        summary="List open pull requests",
    )
    async def list_pull_requests_endpoint(
        jurisdiction_ocdid: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        pull_requests, _, _ = await pull_requests_db.list_open_pull_requests(
            jurisdiction_ocdid=jurisdiction_ocdid
        )
        return {"data": pull_requests}

    # ── Pull Requests: List & Data ───────────
    @router.get(
        "/data",
        summary="Get YAML data from a pull request branch",
    )
    async def get_pull_request_data_endpoint(
        jurisdiction_ocdid: str,
        request_id: str,
        background_tasks: BackgroundTasks,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        file_path = shared.utils.id_utils.jurisdiction_ocdid_to_folder(
            jurisdiction_ocdid
        )

        existing, cached = await asyncio.gather(
            database.people.get_people_by_jurisdiction_ocdid(jurisdiction_ocdid),
            database.pipeline_runs.get_pipeline_run_data_json(request_id),
        )

        # Fast path: serve from DB if already backfilled
        if cached is not None:
            return {
                "request_id": request_id,
                "file_path": file_path,
                "data": cached,
                "existing": existing,
            }

        file_content = await github_service.get_pull_request_file_yaml(
            jurisdiction_ocdid=jurisdiction_ocdid,
            request_id=request_id,
            file_path=f"data/{file_path}.yml",
        )
        if file_content is None:
            # Branch or file not found — trigger a full PR sync in the background
            # so the next request succeeds once the sync completes.
            background_tasks.add_task(pr_sync_service.sync_open_pr_state)
            return JSONResponse(
                content={"error": "Data file not found on branch"}, status_code=404
            )

        # Backfill DB so future requests skip the GitHub roundtrip
        background_tasks.add_task(
            database.pipeline_runs.update_pipeline_run_data, request_id, file_content
        )

        return {
            "request_id": request_id,
            "file_path": file_path,
            "data": file_content,
            "existing": existing,
        }

    # ── Pull Requests: Update Data ───────────

    @router.put("/data", include_in_schema=False)
    async def post_job_pull_request_data_endpoint(
        request: PostJobPullRequestDataRequest,
        background_tasks: BackgroundTasks,
        user: Identity = Depends(require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])),
    ):
        user_name = user.email
        file_path = shared.utils.id_utils.jurisdiction_ocdid_to_folder(
            request.jurisdiction_ocdid
        )
        branch_name = shared.utils.id_utils.make_job_branch(
            request.jurisdiction_ocdid, request.request_id
        )
        normalized = [official.model_dump() for official in request.data]
        _github_response = await github_service.update_pull_request_file(
            branch_name=branch_name,
            file_path=f"data/{file_path}.yml",
            new_data=normalized,
            commit_message=f"Data update by {user_name}",
        )

        # Update the results_json in the background, too
        background_tasks.add_task(
            database.pipeline_runs.update_pipeline_run_data, request.request_id, normalized
        )
        if not _github_response:
            return JSONResponse(
                content=ErrorResponse(
                    error="Failed to update pull request data on GitHub"
                ).model_dump(),
                status_code=500,
            )
        return {"branch_name": branch_name, "status": "success"}

    # ── Pull Requests: Batch Data ────────────
    @router.get(
        "/with-data",
        summary="Batch get pull request details and data",
    )
    async def get_pull_requests_with_data(
        page: int = 1,
        per_page: int = 10,
        state_code: str | None = None,
        jurisdiction_ocdid: str | None = None,
        view: str = Query(default=DEFAULT_VIEW, pattern=f"^({'|'.join(VIEWS)})$"),
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        paged_pull_requests, total, with_issues = await pull_requests_db.list_open_pull_requests(
            state_code=state_code, jurisdiction_ocdid=jurisdiction_ocdid, page=page, per_page=per_page
        )
        total_pages = (total + per_page - 1) // per_page

        jurisdiction_ocdids = list(
            {pr["jurisdiction"]["ocdid"] for pr in paged_pull_requests if pr.get("jurisdiction")}
        )
        request_ids = list({pr["request_id"] for pr in paged_pull_requests})
        data = await database.people.get_people_data_by_request_ids(
            jurisdiction_ocdids, request_ids, view=view
        )

        results = []
        for pr in paged_pull_requests:
            entry = data.get(pr["request_id"], {})
            proposed = entry.get("proposed", [])
            unique_source_urls = list({url for person in proposed for url in (person.get("source_urls") or [])})
            results.append({
                **pr,
                "existing": entry.get("existing", []),
                "proposed": proposed,
                "sources": build_sources(pr["request_id"], pr["jurisdiction"]["ocdid"], unique_source_urls),
            })
        return {
            "data": results,
            "total": total,
            "total_pages": total_pages,
            "page": page,
            "per_page": per_page,
            "summary": {
                "total_with_pr": total,
                "with_issues": with_issues,
            },
        }

    # -- Pull Requests: Issues for a job ---
    @router.get("/{request_id}/review")
    async def get_pull_request_review_endpoint(
        request_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        result = await database.pipeline_runs.get_pipeline_run_result(request_id)
        return {"data": (result or {}).get("review_json") or {}}

    # -- Pull Requests: Close Pull Request ---
    @router.delete("/{pull_request_number}", include_in_schema=False)
    async def close_pull_request_endpoint(
        pull_request_number: str,
        request_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        success = await github_service.close_pull_request(
            pull_request_number=pull_request_number,
        )
        if not success:
            return JSONResponse(
                content=ErrorResponse(
                    error="Failed to close pull request on GitHub"
                ).model_dump(),
                status_code=500,
            )
        user_id = await database.users.get_user_id_by_provider(user.provider, user.provider_user_id)
        await pull_requests_db.update_pipeline_run_pull_request_status(request_id, PullRequestStatus.CLOSED, resolved_by_user_id=user_id)
        return {"status": "success"}

    # -- Pull Requests: Save and Merge ---
    @router.post("/{pull_request_number}/save-and-merge", include_in_schema=False)
    async def save_and_merge_endpoint(
        pull_request_number: str,
        request: SaveAndMergeRequest,
        background_tasks: BackgroundTasks,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        if request.data:
            file_path = shared.utils.id_utils.jurisdiction_ocdid_to_folder(request.jurisdiction_ocdid)
            branch_name = shared.utils.id_utils.make_job_branch(request.jurisdiction_ocdid, request.request_id)
            normalized = [official.model_dump() for official in request.data]
            success = await github_service.update_pull_request_file(
                branch_name=branch_name,
                file_path=f"data/{file_path}.yml",
                new_data=normalized,
                commit_message=f"Data update by {user.email}",
            )
            if not success:
                return JSONResponse(
                    content=ErrorResponse(error="Failed to update pull request data on GitHub").model_dump(),
                    status_code=500,
                )
            background_tasks.add_task(database.pipeline_runs.update_pipeline_run_data, request.request_id, normalized)

        merge_key = f"merge_status:{pull_request_number}"
        await redis_store.set(merge_key, json.dumps({"status": "pending"}), ttl=merge_service.MERGE_STATUS_TTL)
        if not user.user_id:
            raise HTTPException(status_code=401, detail="User ID not available")
        background_tasks.add_task(merge_service.do_merge, pull_request_number, request.request_id, user.email, user.user_id, merge_key)
        return JSONResponse(content={"status": "pending"}, status_code=202)

    # -- Pull Requests: Merge Status ---
    @router.get("/{pull_request_number}/merge-status", include_in_schema=False)
    async def merge_status_endpoint(
        pull_request_number: str,
        _: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        raw = await redis_store.get(f"merge_status:{pull_request_number}")
        if not raw:
            return {"status": "pending"}
        return json.loads(raw)

    # -- Pull Requests: Merge Pull Request ---
    @router.post("/{pull_request_number}/merge", include_in_schema=False)
    async def merge_pull_request_endpoint(
        pull_request_number: str,
        request_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        merge_error = await github_service.merge_pull_request(
            pull_request_number=pull_request_number,
            approved_by=user.email,
        )
        if merge_error:
            status_code = 409 if "out of date" in merge_error.lower() else 500
            return JSONResponse(
                content=ErrorResponse(error=merge_error).model_dump(),
                status_code=status_code,
            )
        user_id = await database.users.get_user_id_by_provider(user.provider, user.provider_user_id)
        await pull_requests_db.update_pipeline_run_pull_request_status(request_id, PullRequestStatus.MERGED, resolved_by_user_id=user_id)
        return {"status": "success"}

    # -- Pull Requests: Update Branch ---
    @router.post("/{pull_request_number}/update-branch", include_in_schema=False)
    async def update_pull_request_branch_endpoint(
        pull_request_number: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        error = await github_service.update_pull_request_branch(
            pull_request_number=pull_request_number,
        )
        if error:
            return JSONResponse(
                content=ErrorResponse(error=error).model_dump(),
                status_code=500,
            )
        return {"status": "success"}

    return router
