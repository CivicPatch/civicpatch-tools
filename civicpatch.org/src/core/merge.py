import asyncio
import json
import logging

import database.pull_requests as pull_requests_db
import lib.github.api as github_service
import lib.redis as redis_store
from shared.utils.statuses import PullRequestStatus

logger = logging.getLogger(__name__)

MERGE_STATUS_TTL = 3600


async def do_merge(pull_request_number: str, request_id: str, approved_by: str | None, user_id: str, merge_key: str) -> None:
    """
    Runs the full merge flow for a pull request and writes the result to Redis.
    Intended to be called as a background task after the HTTP response is sent.
    """
    try:
        mergeable_state = await github_service.get_pull_request_mergeability(pull_request_number)
        logger.info(f"PR {pull_request_number} mergeable_state={mergeable_state!r}")

        if mergeable_state == "dirty":
            await redis_store.set(merge_key, json.dumps({"status": "error", "error": "Pull request has merge conflicts and cannot be merged automatically"}), ttl=MERGE_STATUS_TTL)
            return

        if mergeable_state == "blocked":
            await redis_store.set(merge_key, json.dumps({"status": "error", "error": "Pull request is blocked — required reviews or status checks have not been satisfied"}), ttl=MERGE_STATUS_TTL)
            return

        if mergeable_state == "behind":
            update_error = await github_service.update_pull_request_branch(pull_request_number=pull_request_number)
            if update_error:
                await redis_store.set(merge_key, json.dumps({"status": "error", "error": update_error}), ttl=MERGE_STATUS_TTL)
                return
            mergeable_state = await github_service.get_pull_request_mergeability(pull_request_number, wait_for_change_from="behind")
            logger.info(f"PR {pull_request_number} mergeable_state after branch update={mergeable_state!r}")
            if mergeable_state == "dirty":
                await redis_store.set(merge_key, json.dumps({"status": "error", "error": "Pull request has merge conflicts and cannot be merged automatically"}), ttl=MERGE_STATUS_TTL)
                return

        if mergeable_state != "clean":
            await redis_store.set(merge_key, json.dumps({"status": "error", "error": f"Pull request is not in a mergeable state ({mergeable_state!r})"}), ttl=MERGE_STATUS_TTL)
            return

        merge_error = await github_service.merge_pull_request(pull_request_number=pull_request_number, approved_by=approved_by)

        if merge_error and "base branch was modified" in merge_error.lower():
            # Race condition: base branch updated between mergeability check and merge.
            # PRs touch non-overlapping file paths so updating and retrying almost always succeeds.
            # update-branch returns 202 Accepted (async on GitHub's side), so we sleep before
            # polling mergeability — safe here since this runs in a background task.
            logger.info(f"PR {pull_request_number} base branch modified race condition — updating branch and retrying")
            update_error = await github_service.update_pull_request_branch(pull_request_number=pull_request_number)
            if not update_error:
                await asyncio.sleep(5)
                await github_service.get_pull_request_mergeability(pull_request_number, wait_for_change_from="behind")
                merge_error = await github_service.merge_pull_request(pull_request_number=pull_request_number, approved_by=approved_by)

        if merge_error:
            await redis_store.set(merge_key, json.dumps({"status": "error", "error": merge_error}), ttl=MERGE_STATUS_TTL)
            return

        await pull_requests_db.update_job_pull_request_status(request_id, PullRequestStatus.MERGED, resolved_by_user_id=user_id)
        await redis_store.set(merge_key, json.dumps({"status": "merged"}), ttl=MERGE_STATUS_TTL)

    except Exception as e:
        logger.error(f"Background merge task failed for PR {pull_request_number}: {e}")
        try:
            await redis_store.set(merge_key, json.dumps({"status": "error", "error": "An unexpected error occurred during merge"}), ttl=MERGE_STATUS_TTL)
        except Exception:
            pass
