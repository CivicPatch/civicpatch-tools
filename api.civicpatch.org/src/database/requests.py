import json
from typing import Optional

from database.database import get_pool
from shared.utils.statuses import JobStatus, PullRequestStatus
from utils.github_utils import pull_request_url_to_number


async def register_request_with_job(
    requested_by_provider: str,
    requested_by_provider_user_id: str,
    request_id: str,
    job_type: str,
    arguments_json: dict,
    server_source: Optional[str] = None,
    jurisdiction_ocdid: Optional[str] = None,
    status: JobStatus = JobStatus.PENDING,
    progress: int = 0,
    run_url: Optional[str] = None,
):
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            INSERT INTO requests (status, request_type, jurisdiction_ocdid, arguments_json, created_at, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (status, job_type, jurisdiction_ocdid, json.dumps(arguments_json)),
        )
        request_uuid = (await cur.fetchone())[0]

        cur = await conn.execute(
            """
            INSERT INTO jobs (
                request_id, requested_by_provider, requested_by_provider_user_id,
                status, progress, server_source, run_url,
                created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (request_id, requested_by_provider, requested_by_provider_user_id,
             status, progress, server_source, run_url),
        )
        job_id = (await cur.fetchone())[0]

        await conn.execute(
            "UPDATE requests SET job_id = %s WHERE id = %s",
            (job_id, request_uuid),
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
        cur = await conn.execute(
            """
            INSERT INTO requests (status, request_type, jurisdiction_ocdid, created_at, updated_at)
            VALUES (%s, 'people', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (JobStatus.COMPLETED, jurisdiction_ocdid),
        )
        request_uuid = (await cur.fetchone())[0]

        # Minimal job row so the request can be looked up by its foreign request_id string
        cur = await conn.execute(
            """
            INSERT INTO jobs (
                request_id, requested_by_provider, requested_by_provider_user_id,
                status, progress, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, 100, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (request_id, provider, provider, JobStatus.COMPLETED),
        )
        job_id = (await cur.fetchone())[0]

        await conn.execute(
            "UPDATE requests SET job_id = %s WHERE id = %s",
            (job_id, request_uuid),
        )

        pr_number = 0
        if pr_url:
            num = pull_request_url_to_number(pr_url)
            pr_number = int(num) if num else 0

        cur = await conn.execute(
            """
            INSERT INTO pull_requests (request_id, url, status, pr_number, created_at, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (request_uuid, pr_url, PullRequestStatus.OPEN, pr_number),
        )
        pr_uuid = (await cur.fetchone())[0]

        await conn.execute(
            "UPDATE requests SET pr_id = %s WHERE id = %s",
            (pr_uuid, request_uuid),
        )
