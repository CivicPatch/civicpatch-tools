BEGIN;

-- reviewed_request_ids was the per-session list of resolved request_ids, used by the
-- allocator to skip already-reviewed cards within a session. It is now redundant:
-- publishing parks a PR (merge_enqueued_at) and closing flips its status, so resolved PRs
-- are already excluded from the pool by AVAILABLE_FOR_REVIEW before the allocator runs.
ALTER TABLE review_sessions DROP COLUMN reviewed_request_ids;

COMMIT;
