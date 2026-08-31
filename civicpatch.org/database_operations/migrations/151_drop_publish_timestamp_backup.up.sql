-- Migration 117 is permanent. Drop the snapshot it kept in case it was not.
--
-- 117 re-stamped `published_at` / `dismissed_at` / `resolved_by_user_id` on `requests` from
-- `change_logs`, and kept the prior values here because they cannot be recomputed: 115 had
-- stored `pr.updated_at` as it stood at the time, and pr_sync rewrote that column on every
-- reconciliation, so recomputation yields today's value rather than the one overwritten.
--
-- **This is deliberately irreversible, and the down migration does not pretend otherwise.**
-- Once these rows are gone, 117's down has nothing to restore from. It is dropped on the
-- judgement that 117's values are correct and settled, not because the table was unused —
-- it was unused the way insurance is unused.
--
-- Worth knowing before rolling anything back: **117's up can never run again.** Its lines 65
-- and 74 read `FROM review_times v, pull_requests pr`, and migration 141 dropped
-- `pull_requests`. So rolling 117 back was already a one-way door before this migration; this
-- one removes the door.
--
-- The shape, for anyone reconstructing it from a database backup:
--
--     publish_timestamp_backup_117 (
--         request_id          uuid PRIMARY KEY REFERENCES requests(id) ON DELETE CASCADE,
--         published_at        timestamptz,
--         dismissed_at        timestamptz,
--         resolved_by_user_id uuid
--     )
BEGIN;

DROP TABLE IF EXISTS publish_timestamp_backup_117;

COMMIT;
