import json
from typing import Optional

from database.database import get_pool
from shared.utils.statuses import JobStatus, PullRequestStatus
from utils.github_utils import pull_request_url_to_number


async def register_request_with_job(
    request_id: str,
    job_type: str,
    arguments_json: dict,
    jurisdiction_ocdid: Optional[str] = None,
    requested_by_user_id: Optional[str] = None,
    status: JobStatus = JobStatus.PENDING,
    progress: int = 0,
):
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO requests (id, request_type, jurisdiction_ocdid, arguments_json, requested_by_user_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (request_id, job_type, jurisdiction_ocdid, json.dumps(arguments_json), requested_by_user_id),
        )

        await conn.execute(
            """
            INSERT INTO jobs (
                request_id, status, progress,
                created_at, updated_at
            )
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (request_id, status, progress),
        )


async def register_foreign_request(
    request_id: str,
    jurisdiction_ocdid: str,
    pr_url: Optional[str],
    provider: str,
):
    """
    Create a request + pull_request record for a PR that has no backing job worker.
    The request_id is "foreign" — derived from the git branch name, not our job pipeline.
    Used by the GitHub webhook handler and hourly PR sync.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """
            INSERT INTO requests (id, request_type, jurisdiction_ocdid, created_at, updated_at)
            VALUES (%s, 'people', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (request_id, jurisdiction_ocdid),
        )

        # Minimal job row so the request can be looked up by its foreign request_id string
        await conn.execute(
            """
            INSERT INTO jobs (
                request_id, status, progress, created_at, updated_at
            )
            VALUES (%s, %s, 100, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (request_id, JobStatus.COMPLETED),
        )

        pr_number = 0
        if pr_url:
            num = pull_request_url_to_number(pr_url)
            pr_number = int(num) if num else 0

        await conn.execute(
            """
            INSERT INTO pull_requests (request_id, url, status, pr_number, created_at, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (request_id, pr_url, PullRequestStatus.OPEN, pr_number),
        )
