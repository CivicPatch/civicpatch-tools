import logging

import database.database as database
import services.github.github_api_service as github_service
import shared.utils.id_utils
from utils.github_utils import pull_request_url_to_number

logger = logging.getLogger(__name__)


async def sync_open_pr_state():
    logger.info("sync_open_pr_state: starting")
    github_prs = await _fetch_open_github_prs()
    await _sync_known_prs(github_prs)
    await _close_stale_prs(set(github_prs.keys()))
    logger.info("sync_open_pr_state: done")


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
    await database.register_job(
        requested_by_provider=provider,
        requested_by_provider_user_id=provider,
        request_id=request_id,
        job_type="people",
        arguments_json={"jurisdiction_ocdid": jurisdiction_ocdid},
        jurisdiction_ocdid=jurisdiction_ocdid,
        status="COMPLETED",
        progress=100,
    )
    await database.update_job_pull_request_status(request_id, "open", None, pull_request_url=pr_url)
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
            request_id, "open", None, pull_request_url=pr_info["url"]
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
    db_open_jobs = await database.get_open_pr_request_ids()
    stale_ids = [rid for rid in db_open_jobs if rid not in github_request_ids]
    if not stale_ids:
        return
    logger.info("sync_open_pr_state: resolving %d stale PR(s)", len(stale_ids))
    for request_id in stale_ids:
        pr_url = db_open_jobs[request_id]
        pr_number = pull_request_url_to_number(pr_url) if pr_url else None
        status, merged_at = "closed", None
        if pr_number:
            pr_data = await github_service.get_pull_request(pr_number)
            if pr_data and pr_data.get("merged"):
                status, merged_at = "merged", pr_data.get("merged_at")
        await database.update_job_pull_request_status(request_id, status, merged_at)
