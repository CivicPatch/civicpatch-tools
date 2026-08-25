BEGIN;

-- Nothing opens a pull request for a scrape any more: approving commits straight to
-- open-data's default branch, and the merge queue that needed a row to track is gone.
--
-- Every column already had a home on `requests` or died with PRs: `status` is
-- published_at/dismissed_at, `merged_at` is published_at, `resolved_by_user_id` is
-- duplicated there, and `merge_enqueued_at` belonged to the queue. So this drops a
-- projection, not a fact.
DROP TABLE IF EXISTS pull_requests;

COMMIT;
