import json
import logging

import database.issues as issues_db
import database.pull_requests as pull_requests_db
import lib.github.api as github_service
import lib.redis as redis_store
from shared.utils.statuses import PipelineIssueType, PullRequestStatus

logger = logging.getLogger(__name__)

MERGE_STATUS_TTL = 3600

# A merge that stays parked past this window never settled: do_merge — which records its
# own failure as an issue — never ran (e.g. the merge worker is down). 15 min is well clear
# of a healthy merge (seconds) so an in-flight one is never flagged.
STUCK_MERGE_AFTER_MINUTES = 15
STUCK_MERGE_SWEEP_INTERVAL_SECONDS = 60


async def _handle_failure(merge_key: str, request_id: str, error: str, mergeable_state: str | None = None) -> None:
    # A failed merge no longer means unpublished data — publishing happened at the review
    # endpoint, so only the open-data artifact is missing. Still parked and still raised as an
    # issue, with mergeable_state so the details page can show why (blocked vs dirty vs a null
    # poll timeout vs clean-but-GitHub-refused), not just a request id.
    await redis_store.set(merge_key, json.dumps({"status": "error", "error": error}), ttl=MERGE_STATUS_TTL)
    await issues_db.upsert_issue(
        request_id, PipelineIssueType.MERGE_FAILED, [{"error": error, "mergeable_state": mergeable_state}]
    )


async def do_merge(pull_request_number: str, request_id: str, approved_by: str | None, user_id: str, merge_key: str) -> None:
    try:
        mergeable_state = await github_service.get_pull_request_mergeability(pull_request_number)
        logger.info(f"PR {pull_request_number} mergeable_state={mergeable_state!r}")

        if mergeable_state == "dirty":
            await _handle_failure(merge_key, request_id, "Pull request has merge conflicts and cannot be merged automatically", mergeable_state)
            return

        if mergeable_state == "blocked":
            await _handle_failure(merge_key, request_id, "Pull request is blocked — required reviews or status checks have not been satisfied", mergeable_state)
            return

        if mergeable_state == "behind":
            update_error = await github_service.update_pull_request_branch(pull_request_number=pull_request_number)
            if update_error:
                await _handle_failure(merge_key, request_id, update_error, mergeable_state)
                return
            mergeable_state = await github_service.get_pull_request_mergeability(pull_request_number, wait_for_change_from="behind")
            logger.info(f"PR {pull_request_number} mergeable_state after branch update={mergeable_state!r}")
            if mergeable_state == "dirty":
                await _handle_failure(merge_key, request_id, "Pull request has merge conflicts and cannot be merged automatically", mergeable_state)
                return

        if mergeable_state != "clean":
            await _handle_failure(merge_key, request_id, f"Pull request is not in a mergeable state ({mergeable_state!r})", mergeable_state)
            return

        merge_error = await github_service.merge_pull_request(pull_request_number=pull_request_number, approved_by=approved_by)

        if merge_error:
            await _handle_failure(merge_key, request_id, merge_error, mergeable_state)
            return

        await pull_requests_db.update_pull_request_status(request_id, PullRequestStatus.MERGED, resolved_by_user_id=user_id)
        await pull_requests_db.clear_merge_enqueued(request_id)
        await redis_store.set(merge_key, json.dumps({"status": "merged"}), ttl=MERGE_STATUS_TTL)

    except Exception as e:
        logger.error(f"Background merge task failed for PR {pull_request_number}: {e}")
        try:
            await _handle_failure(merge_key, request_id, "An unexpected error occurred during merge")
        except Exception:
            pass
