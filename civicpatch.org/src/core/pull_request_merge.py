import json
import logging

import core.change_logs as change_logs
import core.pull_request_sync as pull_request_sync
import database.pull_requests as pull_requests_db
import lib.github.api as github_service
import lib.redis as redis_store
from shared.utils.statuses import PullRequestStatus

logger = logging.getLogger(__name__)

MERGE_STATUS_TTL = 3600


async def _handle_failure(merge_key: str, request_id: str, error: str) -> None:
    # A failed merge must both report to the client (Redis) and clear the in-flight mark
    # so the PR returns to the available queue.
    await redis_store.set(merge_key, json.dumps({"status": "error", "error": error}), ttl=MERGE_STATUS_TTL)
    await pull_requests_db.clear_merge_enqueued(request_id)


async def do_merge(pull_request_number: str, request_id: str, approved_by: str | None, user_id: str, merge_key: str) -> None:
    try:
        mergeable_state = await github_service.get_pull_request_mergeability(pull_request_number)
        logger.info(f"PR {pull_request_number} mergeable_state={mergeable_state!r}")

        if mergeable_state == "dirty":
            await _handle_failure(merge_key, request_id, "Pull request has merge conflicts and cannot be merged automatically")
            return

        if mergeable_state == "blocked":
            await _handle_failure(merge_key, request_id, "Pull request is blocked — required reviews or status checks have not been satisfied")
            return

        if mergeable_state == "behind":
            update_error = await github_service.update_pull_request_branch(pull_request_number=pull_request_number)
            if update_error:
                await _handle_failure(merge_key, request_id, update_error)
                return
            mergeable_state = await github_service.get_pull_request_mergeability(pull_request_number, wait_for_change_from="behind")
            logger.info(f"PR {pull_request_number} mergeable_state after branch update={mergeable_state!r}")
            if mergeable_state == "dirty":
                await _handle_failure(merge_key, request_id, "Pull request has merge conflicts and cannot be merged automatically")
                return

        if mergeable_state != "clean":
            await _handle_failure(merge_key, request_id, f"Pull request is not in a mergeable state ({mergeable_state!r})")
            return

        merge_error = await github_service.merge_pull_request(pull_request_number=pull_request_number, approved_by=approved_by)

        if merge_error:
            await _handle_failure(merge_key, request_id, merge_error)
            return

        await pull_requests_db.update_pull_request_status(request_id, PullRequestStatus.MERGED, resolved_by_user_id=user_id)
        await pull_requests_db.clear_merge_enqueued(request_id)
        await redis_store.set(merge_key, json.dumps({"status": "merged"}), ttl=MERGE_STATUS_TTL)
        await change_logs.record_publish(request_id, user_id)

        # Resolve the review entry + sync open data. Best-effort and isolated so a failure
        # here can't turn a successful merge into a reported error. Idempotent, so a webhook
        # racing in for the same PR is harmless.
        try:
            pr = await github_service.get_pull_request(pull_request_number)
            pr_labels = pr.get("labels", []) if pr else []
            await pull_request_sync.publish_side_effects(request_id, PullRequestStatus.MERGED, pr_labels)
        except Exception:
            logger.exception(f"Publish side effects failed after merging PR {pull_request_number}")

    except Exception as e:
        logger.error(f"Background merge task failed for PR {pull_request_number}: {e}")
        try:
            await _handle_failure(merge_key, request_id, "An unexpected error occurred during merge")
        except Exception:
            pass
