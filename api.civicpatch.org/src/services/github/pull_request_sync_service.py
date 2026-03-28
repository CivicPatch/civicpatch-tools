import logging

import database.database as database
import database.pull_requests as pull_requests_db
import database.requests as requests_db
import services.github.github_api_service as github_service
import services.lock_service as lock_service
import shared.utils.id_utils
from shared.utils.statuses import PullRequestStatus
from utils.github_utils import pull_request_url_to_number

logger = logging.getLogger(__name__)

_SYNC_LOCK_KEY = "lock:sync_open_pr_state"
_SYNC_LOCK_TTL = 1800  # 30 min — longer than any expected sync duration


async def sync_single_pr_state(request_id: str):
    pr_metadata = await pull_requests_db.get_pull_request_for_review(request_id)
    if not pr_metadata:
        return
    pull_request_url = pr_metadata.get("pull_request_url")
    pr_number = pull_request_url_to_number(pull_request_url) if pull_request_url else None
    if not pr_number:
        return
    pr_data = await github_service.get_pull_request(pr_number)
    if not pr_data:
        return
    if pr_data.get("merged"):
        await database.update_job_pull_request_status(request_id, PullRequestStatus.MERGED, pr_data.get("merged_at"))
    elif pr_data.get("state") == PullRequestStatus.CLOSED:
        await database.update_job_pull_request_status(request_id, PullRequestStatus.CLOSED, None)
    else:
        review_state = await github_service.get_pull_request_review_state(pr_number)
        await database.update_job_pull_request_review_state(request_id, review_state)


async def sync_open_pr_state():
    acquired = await lock_service.acquire_lock(_SYNC_LOCK_KEY, _SYNC_LOCK_TTL)
    if not acquired:
        logger.info("sync_open_pr_state: skipping, lock held by another worker")
        return
    try:
        logger.info("sync_open_pr_state: starting")
        github_prs = await _fetch_open_github_prs()
        await _sync_known_prs(github_prs)
        await _close_stale_prs(set(github_prs.keys()))
        logger.info("sync_open_pr_state: done")
    finally:
        await lock_service.release_lock(_SYNC_LOCK_KEY)


async def maybe_backfill_job_result(request_id: str, jurisdiction_ocdid: str):
    result = await database.get_job_result(request_id)
    if result is None:
        return

    if result["data"] is None:
        folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
        data = await github_service.get_pull_request_file_yaml(
            request_id, jurisdiction_ocdid, f"data/{folder}.yml"
        )
        if data is None:
            logger.warning("maybe_backfill_job_result: no data file found for %s", request_id)
        else:
            await database.update_job_data(request_id, data)
            logger.info("maybe_backfill_job_result: data_json set for %s", request_id)

    if not result["review_json"]:
        workflow_context = await github_service.get_pull_request_workflow_context(request_id, jurisdiction_ocdid)
        review_json = _derive_review_step(workflow_context)
        await database.update_job_review_json(request_id, review_json)
        logger.info("maybe_backfill_job_result: review_json set for %s", request_id)


def _derive_review_step(workflow_context) -> dict:
    if not workflow_context:
        return {}
    return workflow_context.get("data", {}) \
        .get("review_output_step", {})


async def register_and_sync_pr_job(
    request_id: str,
    jurisdiction_ocdid: str,
    pr_url: str | None,
    provider: str,
):
    await requests_db.register_foreign_request(request_id, jurisdiction_ocdid, pr_url, provider)
    await maybe_backfill_job_result(request_id, jurisdiction_ocdid)


async def _fetch_open_github_prs() -> dict[str, dict]:
    github_prs: dict[str, dict] = {}
    for pr in await github_service.get_all_open_prs_raw():
        branch_name = pr.get("head", {}).get("ref", "")
        try:
            parts = shared.utils.id_utils.git_branch_to_parts(branch_name)
            github_prs[parts["request_id"]] = {
                "url": pr.get("html_url"),
                "jurisdiction_ocdid": parts["jurisdiction_ocdid"],
                "pr_number": pr.get("number"),
            }
        except (ValueError, KeyError):
            pass
    logger.info("sync_open_pr_state: found %d open PRs on GitHub", len(github_prs))
    return github_prs


async def _sync_known_prs(github_prs: dict[str, dict]):
    for request_id, pr_info in github_prs.items():
        updated = await database.update_job_pull_request_status(
            request_id, PullRequestStatus.OPEN, None, pull_request_url=pr_info["url"]
        )
        if not updated:
            logger.info("sync_open_pr_state: no job found for %s, creating", request_id)
            await register_and_sync_pr_job(
                request_id,
                pr_info["jurisdiction_ocdid"],
                pr_info["url"],
                provider="github_sync",
            )
        else:
            await maybe_backfill_job_result(request_id, pr_info["jurisdiction_ocdid"])
        if pr_info.get("pr_number"):
            review_state = await github_service.get_pull_request_review_state(pr_info["pr_number"])
            await database.update_job_pull_request_review_state(request_id, review_state)


async def _close_stale_prs(github_request_ids: set[str]):
    if not github_request_ids:
        logger.warning("_close_stale_prs: skipping, github_request_ids is empty")
        return
    db_open_jobs = await database.get_open_pr_request_ids()
    stale_ids = [rid for rid in db_open_jobs if rid not in github_request_ids]
    if not stale_ids:
        return
    logger.info("sync_open_pr_state: resolving %d stale PR(s)", len(stale_ids))
    for request_id in stale_ids:
        pr_url = db_open_jobs[request_id]
        pr_number = pull_request_url_to_number(pr_url) if pr_url else None
        status, merged_at = None, None
        if pr_number:
            pr_data = await github_service.get_pull_request(pr_number)
            if pr_data and pr_data.get("merged"):
                status, merged_at = PullRequestStatus.MERGED, pr_data.get("merged_at")
            elif pr_data and pr_data.get("state") == PullRequestStatus.CLOSED:
                status = PullRequestStatus.CLOSED
            if status:
                await database.update_job_pull_request_status(request_id, status, merged_at)
