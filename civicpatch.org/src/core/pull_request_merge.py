import json
import logging

import database.pull_requests as pull_requests_db
import lib.github.api as github_service
import lib.redis as redis_store
from shared.utils.statuses import PullRequestStatus

logger = logging.getLogger(__name__)

MERGE_STATUS_TTL = 3600


async def _record_failure(merge_key: str, error: str) -> None:
    await redis_store.set(merge_key, json.dumps({"status": "error", "error": error}), ttl=MERGE_STATUS_TTL)


async def do_merge(pull_request_number: str, request_id: str, approved_by: str | None, user_id: str, merge_key: str) -> None:
    try:
        mergeable_state = await github_service.get_pull_request_mergeability(pull_request_number)
        logger.info(f"PR {pull_request_number} mergeable_state={mergeable_state!r}")

        if mergeable_state == "dirty":
            await _record_failure(merge_key, "Pull request has merge conflicts and cannot be merged automatically")
            return

        if mergeable_state == "blocked":
            await _record_failure(merge_key, "Pull request is blocked — required reviews or status checks have not been satisfied")
            return

        if mergeable_state == "behind":
            update_error = await github_service.update_pull_request_branch(pull_request_number=pull_request_number)
            if update_error:
                await _record_failure(merge_key, update_error)
                return
            mergeable_state = await github_service.get_pull_request_mergeability(pull_request_number, wait_for_change_from="behind")
            logger.info(f"PR {pull_request_number} mergeable_state after branch update={mergeable_state!r}")
            if mergeable_state == "dirty":
                await _record_failure(merge_key, "Pull request has merge conflicts and cannot be merged automatically")
                return

        if mergeable_state != "clean":
            await _record_failure(merge_key, f"Pull request is not in a mergeable state ({mergeable_state!r})")
            return

        merge_error = await github_service.merge_pull_request(pull_request_number=pull_request_number, approved_by=approved_by)

        if merge_error:
            await _record_failure(merge_key, merge_error)
            return

        await pull_requests_db.update_pipeline_run_pull_request_status(request_id, PullRequestStatus.MERGED, resolved_by_user_id=user_id)
        await redis_store.set(merge_key, json.dumps({"status": "merged"}), ttl=MERGE_STATUS_TTL)

    except Exception as e:
        logger.error(f"Background merge task failed for PR {pull_request_number}: {e}")
        try:
            await _record_failure(merge_key, "An unexpected error occurred during merge")
        except Exception:
            pass
