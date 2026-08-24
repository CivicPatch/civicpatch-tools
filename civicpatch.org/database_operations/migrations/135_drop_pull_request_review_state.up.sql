BEGIN;

-- `review_state` never had a writer that anything called.
--
-- 039 moved it here from `pipeline_runs` and 056 left it alone. The one function that sets it,
-- `update_pipeline_run_pull_request_review_state`, has no call site anywhere in the codebase —
-- so every row is NULL, on dev and in production, and always has been.
--
-- Not the same thing as the request's review lifecycle, which lives on `requests`
-- (`published_at` / `dismissed_at` / `dismissed_reason`) and is read constantly. This column
-- is a second, empty answer to a question already answered elsewhere, which is the reason to
-- remove it rather than find it a writer.
ALTER TABLE pull_requests DROP COLUMN review_state;

COMMIT;
