import logging

import database.pipeline_runs as jobs_db
import database.issues as issues_db
import database.pull_requests as pull_requests_db
import database.requests as requests_db
import database.review_sessions as review_sessions_db
import lib.github.api as github_service
import lib.lock as lock_service
import shared.utils.id_utils
from core.open_data_sync import sync_people_by_ocdids
from shared.utils.statuses import PullRequestStatus
from lib.github.utils import pull_request_url_to_number

logger = logging.getLogger(__name__)


async def publish_side_effects(request_id: str, status: str) -> None:
    """Sync open data live when a job PR is merged.

    Review credit (resolving the session entry) is NOT done here — it happens
    synchronously at the publish/close endpoints, the moment the reviewer acts.
    This keeps data-sync (a consequence of the merge) separate from credit (a
    consequence of the review), and means external merges sync data without
    ever crediting a user we can't identify.
    """
    if status != PullRequestStatus.MERGED:
        return
    jurisdiction_ocdid = await requests_db.get_request_jurisdiction(request_id)
    if jurisdiction_ocdid:
        await sync_people_by_ocdids([jurisdiction_ocdid])


async def apply_pull_request_status(
    request_id: str,
    status: str,
    *,
    merged_at=None,
    pull_request_url: str | None = None,
    resolved_by_user_id: str | None = None,
) -> bool:
    """Write a PR's status and, only if it actually transitioned, run the publish side
    effects once. Every status-change path funnels through here so a PR is credited and
    synced exactly once, no matter which path (publish, webhook, reconciliation) sees it first.

    A PR is only synced if its request exists in this server's DB (update returns truthy),
    which is what isolates environments that share a repo — no env label needed."""
    previous_status = await pull_requests_db.get_pull_request_status(request_id)
    written = await pull_requests_db.update_pull_request_status(
        request_id, status, merged_at, pull_request_url, resolved_by_user_id
    )
    changed = written and previous_status != status
    if changed:
        await publish_side_effects(request_id, status)
    return changed


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
        await apply_pull_request_status(request_id, PullRequestStatus.MERGED, merged_at=pr_data.get("merged_at"))
    elif pr_data.get("state") == PullRequestStatus.CLOSED:
        await apply_pull_request_status(request_id, PullRequestStatus.CLOSED)


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
        await sync_issue_pr_state()
        logger.info("sync_open_pr_state: done")
    finally:
        await lock_service.release_lock(_SYNC_LOCK_KEY)


async def sync_issue_pr_state():
    issues = await issues_db.get_issues_with_open_pr()
    if not issues:
        return
    logger.info("sync_issue_pr_state: checking %d open issue PR(s)", len(issues))
    for issue in issues:
        pr_number = pull_request_url_to_number(issue["pull_request_url"])
        if not pr_number:
            continue
        pr_data = await github_service.get_pull_request(pr_number)
        if not pr_data:
            continue
        if pr_data.get("merged"):
            await issues_db.resolve_issue(issue["id"])
            logger.info("sync_issue_pr_state: resolved issue %s (PR merged)", issue["id"])
        elif pr_data.get("state") == "closed":
            await issues_db.reopen_issue(issue["id"])
            logger.info("sync_issue_pr_state: reopened issue %s (PR closed)", issue["id"])


async def maybe_backfill_job_result(request_id: str):
    result = await jobs_db.get_pipeline_run_result(request_id)
    if result is None:
        return

    jurisdiction_ocdid = await requests_db.get_request_jurisdiction(request_id)
    if not jurisdiction_ocdid:
        logger.warning("maybe_backfill_job_result: no jurisdiction found for %s", request_id)
        return

    if result["data"] is None:
        folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
        data = await github_service.get_pull_request_file_yaml(
            request_id, jurisdiction_ocdid, f"data/{folder}.yml"
        )
        if data is None:
            logger.warning("maybe_backfill_job_result: no data file found for %s", request_id)
        else:
            await jobs_db.update_pipeline_run_data(request_id, data)
            logger.info("maybe_backfill_job_result: data_json set for %s", request_id)

    if not result["review_json"]:
        workflow_context = await github_service.get_pull_request_context(request_id, jurisdiction_ocdid)
        review_json = _derive_review_step(workflow_context)
        await jobs_db.update_pipeline_run_review_json(request_id, review_json)
        logger.info("maybe_backfill_job_result: review_json set for %s", request_id)


def _derive_review_step(workflow_context) -> dict:
    if not workflow_context:
        return {}
    return workflow_context.get("data", {}) \
        .get("review_output_step", {})



async def _fetch_open_github_prs() -> dict[str, dict]:
    github_prs: dict[str, dict] = {}
    for pr in await github_service.get_all_open_prs_raw():
        branch_name = pr.get("head", {}).get("ref", "")
        try:
            parts = shared.utils.id_utils.git_branch_to_parts(branch_name)
            github_prs[parts["request_id"]] = {
                "url": pr.get("html_url"),
                "pr_number": pr.get("number"),
            }
        except ValueError:
            pass
    logger.info("sync_open_pr_state: found %d open PRs on GitHub", len(github_prs))
    return github_prs


async def _sync_known_prs(github_prs: dict[str, dict]):
    for request_id, pr_info in github_prs.items():
        updated = await pull_requests_db.update_pull_request_status(
            request_id, PullRequestStatus.OPEN, None, pull_request_url=pr_info["url"]
        )
        if updated:
            await maybe_backfill_job_result(request_id)
        else:
            logger.debug("sync_open_pr_state: no job found for %s, skipping", request_id)


async def _close_stale_prs(github_request_ids: set[str]):
    if not github_request_ids:
        logger.warning("_close_stale_prs: skipping, github_request_ids is empty")
        return
    db_open_jobs = await pull_requests_db.get_open_pr_request_ids()
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
                await apply_pull_request_status(request_id, status, merged_at=merged_at)
