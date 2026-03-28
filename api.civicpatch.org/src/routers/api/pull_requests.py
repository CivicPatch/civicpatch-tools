import os
import asyncio
import logging
from typing import List
from shared.schemas import Official
import services.storage_service
import shared.utils.data_path_utils
import shared.utils.url_utils

import shared.utils.id_utils
from shared.utils.statuses import PullRequestStatus
import yaml
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Query,
)
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import database.database
import database.jobs
import database.people
import database.pull_requests as pull_requests_db
import database.review_sessions as review_sessions_db
import services.github.github_api_service as github_service
import services.github.pull_request_sync_service as pr_sync_service
from database.people import DEFAULT_VIEW, VIEWS
from schemas.common import Identity, Role, RouteCategory
from utils.auth_utils import require_route_access

logger = logging.getLogger(__name__)

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
            database.database.get_job_data_json(request_id),
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
            database.database.update_job_data, request_id, file_content
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
        branch_name = shared.utils.id_utils.make_git_branch(
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
            database.database.update_job_data, request.request_id, normalized
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
        view: str = Query(default=DEFAULT_VIEW, pattern=f"^({'|'.join(VIEWS)})$"),
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        paged_pull_requests, total, changes_requested = await pull_requests_db.list_open_pull_requests(
            state_code=state_code, page=page, per_page=per_page
        )
        total_pages = (total + per_page - 1) // per_page

        jurisdiction_ocdids = list(
            {pr["jurisdiction_ocdid"] for pr in paged_pull_requests if pr.get("jurisdiction_ocdid")}
        )
        request_ids = list({pr["request_id"] for pr in paged_pull_requests})
        data = await database.people.get_people_data_by_request_ids(
            jurisdiction_ocdids, request_ids, view=view
        )

        results = [
            {
                "details": pr,
                "existing": data.get(pr["request_id"], {}).get("existing", []),
                "pull_request": data.get(pr["request_id"], {}).get("pull_request", []),
            }
            for pr in paged_pull_requests
        ]
        return {
            "data": results,
            "total": total,
            "total_pages": total_pages,
            "page": page,
            "per_page": per_page,
            "summary": {
                "total_with_pr": total,
                "changes_requested": changes_requested,
            },
        }

    def _source_url_to_markdown_url(request_id, jurisdiction_ocdid_folder, source_url: str) -> str:
        # For now, let's assume the markdown url is the same as the source url but with "/markdown" appended
        # In the future, this could be a more complex transformation or lookup
        source_url_dir = shared.utils.url_utils.format_url_to_folder(source_url)
        relative_path = os.path.join(request_id, "data_source", jurisdiction_ocdid_folder, "cache", source_url_dir, "preprocessed.md")
        return services.storage_service.get_civicpatch_artifacts_url(relative_path)

    def _source_urls_to_sources(request_id: str, jurisdiction_ocdid: str, source_urls: list[str]) -> list[str]:
        # For every source URL, let's figure out the markdown url
        # The URL will be under storage_service.get_url(bucket, key) where bucket is "civicpatch-artifacts" 
        # and key is "{request_id}/{jurisdiction_ocdid_folder}/{filename}"
        jurisdiction_ocd_id_folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
        return [
            {
                "source_url": url, 
                "markdown_url": _source_url_to_markdown_url(request_id, jurisdiction_ocd_id_folder, url)
            }
            for url in source_urls
        ]

    @router.get("/{request_id}/detail")
    async def get_pull_request_detail(
        request_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        pr_metadata = await database.pull_requests.get_pull_request_for_review(request_id)
        if not pr_metadata:
            raise HTTPException(status_code=404, detail="Pull request not found")

        jurisdiction_ocdid = pr_metadata["jurisdiction_ocdid"]
        folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)

        existing, pull_request = await asyncio.gather(
            database.people.get_people_by_jurisdiction_ocdid(jurisdiction_ocdid),
            database.database.get_job_data_json(request_id),
        )

        if pull_request is None:
            pull_request = await github_service.get_pull_request_file_yaml(
                request_id=request_id,
                jurisdiction_ocdid=jurisdiction_ocdid,
                file_path=f"data/{folder}.yml",
            )
            if pull_request is not None:
                background_tasks.add_task(database.database.update_job_data, request_id, pull_request)

        pull_request = pull_request or []
        unique_source_urls = list({url for person in pull_request for url in (person.get("source_urls") or [])})
        sources = _source_urls_to_sources(request_id, jurisdiction_ocdid, unique_source_urls)

        return {
            "data": {
                "request": pr_metadata,
                "existing": existing,
                "pull_request": pull_request,
                "sources": sources,
            }
        }

    # -- Pull Requests: Issues for a job ---
    @router.get("/{request_id}/review")
    async def get_pull_request_review_endpoint(
        request_id: str,
        user: Identity = Depends(
            require_route_access(RouteCategory.TEAM_REQUIRED, [Role.DEFAULT])
        ),
    ):
        result = await database.database.get_job_result(request_id)
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
        user_id = await database.database.get_user_id_by_provider(user.provider, user.provider_user_id)
        await database.database.update_job_pull_request_status(request_id, PullRequestStatus.CLOSED, resolved_by_user_id=user_id)
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
            branch_name = shared.utils.id_utils.make_git_branch(request.jurisdiction_ocdid, request.request_id)
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
            background_tasks.add_task(database.database.update_job_data, request.request_id, normalized)

        mergeable_state = await github_service.get_pull_request_mergeability(pull_request_number)
        if mergeable_state == "dirty":
            return JSONResponse(
                content=ErrorResponse(error="Pull request has merge conflicts and cannot be merged automatically").model_dump(),
                status_code=422,
            )

        merge_error = await github_service.merge_pull_request(pull_request_number=pull_request_number, approved_by=user.email)

        if merge_error and "out of date" in merge_error.lower():
            update_error = await github_service.update_pull_request_branch(pull_request_number=pull_request_number)
            if update_error:
                return JSONResponse(
                    content=ErrorResponse(error=update_error).model_dump(),
                    status_code=500,
                )
            await github_service.get_pull_request_mergeability(pull_request_number)
            merge_error = await github_service.merge_pull_request(pull_request_number=pull_request_number, approved_by=user.email)

        if merge_error:
            return JSONResponse(
                content=ErrorResponse(error=merge_error).model_dump(),
                status_code=500,
            )

        user_id = await database.database.get_user_id_by_provider(user.provider, user.provider_user_id)
        await database.database.update_job_pull_request_status(request.request_id, PullRequestStatus.MERGED, resolved_by_user_id=user_id)
        return {"status": "success"}

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
        user_id = await database.database.get_user_id_by_provider(user.provider, user.provider_user_id)
        await database.database.update_job_pull_request_status(request_id, PullRequestStatus.MERGED, resolved_by_user_id=user_id)
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
