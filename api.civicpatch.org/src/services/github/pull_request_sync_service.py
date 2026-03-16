import logging

import httpx

import database.database as database
import services.github.github_api_service as github_service
import shared.utils.id_utils
from shared.utils.review_utils import has_data_issues

logger = logging.getLogger(__name__)


async def backfill_job_result(request_id: str, jurisdiction_ocdid: str):
    folder = shared.utils.id_utils.jurisdiction_ocdid_to_folder(jurisdiction_ocdid)
    data = await github_service.get_pull_request_file_yaml(
        request_id, jurisdiction_ocdid, f"data/{folder}.yml"
    )
    if data is None:
        logger.warning("backfill_job_result: no file found for %s", request_id)
        return
    await database.update_job_result(request_id, data, has_issues=has_data_issues(data or []))
    logger.info("backfill_job_result: result_json set for %s", request_id)


async def register_and_sync_pr_job(
    request_id: str,
    jurisdiction_ocdid: str,
    pr_url: str | None,
    provider: str,
    status: str = "pending",
    progress: int = 0,
):
    await database.register_job(
        requested_by_provider=provider,
        requested_by_provider_user_id=provider,
        request_id=request_id,
        job_type="people",
        arguments_json={"jurisdiction_ocdid": jurisdiction_ocdid},
        jurisdiction_ocdid=jurisdiction_ocdid,
        status=status,
        progress=progress,
    )
    await database.update_job_pull_request_status(request_id, "open", None, pull_request_url=pr_url)
    await backfill_job_result(request_id, jurisdiction_ocdid)


async def sync_open_pr_state():
    logger.info("sync_open_pr_state: starting")
    _, _, _, open_data_repo_url = github_service._get_github_config()
    github_request_ids: set[str] = set()
    page = 1
    per_page = 100

    # request_id -> {url, jurisdiction_ocdid}
    github_prs: dict[str, dict] = {}

    while True:
        url = f"{open_data_repo_url}/pulls?state=open&per_page={per_page}&page={page}"
        headers = await github_service.get_default_headers()
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.get(url, headers=headers)

        if response.status_code != 200:
            logger.error(f"sync_open_pr_state: GitHub API error on page {page}: {response.status_code}")
            break

        prs = response.json()
        for pr in prs:
            branch_name = pr.get("head", {}).get("ref", "")
            try:
                parts = shared.utils.id_utils.git_branch_to_parts(branch_name)
                github_prs[parts["request_id"]] = {
                    "url": pr.get("html_url"),
                    "jurisdiction_ocdid": parts["jurisdiction_ocdid"],
                }
            except (ValueError, KeyError):
                pass

        if len(prs) < per_page:
            break
        page += 1

    github_request_ids = set(github_prs.keys())
    logger.info(f"sync_open_pr_state: found {len(github_request_ids)} open PRs on GitHub")

    for request_id, pr_info in github_prs.items():
        updated = await database.update_job_pull_request_status(
            request_id, "open", None, pull_request_url=pr_info["url"]
        )
        if not updated:
            logger.info(f"sync_open_pr_state: no job found for {request_id}, creating")
            await register_and_sync_pr_job(
                request_id,
                pr_info["jurisdiction_ocdid"],
                pr_info["url"],
                provider="github_sync",
                status="completed",
                progress=100,
            )

    db_open_ids = await database.get_open_pr_request_ids()
    stale_ids = [rid for rid in db_open_ids if rid not in github_request_ids]
    if stale_ids:
        logger.info(f"sync_open_pr_state: closing {len(stale_ids)} stale PR(s)")
        await database.bulk_close_stale_prs(stale_ids)

    logger.info("sync_open_pr_state: done")
