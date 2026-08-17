-- Give back exactly the values the up migration replaced.
--
-- Restores from the snapshot rather than recomputing 115's ladder. Recomputation looks
-- equivalent and is not: 115 stored `pr.updated_at` as it stood at the time, and pr_sync
-- rewrites that column on every reconciliation, so recomputing yields today's value instead of
-- the one that was overwritten.
BEGIN;

UPDATE requests r
   SET published_at        = b.published_at,
       dismissed_at        = b.dismissed_at,
       resolved_by_user_id = b.resolved_by_user_id
  FROM publish_timestamp_backup_117 b
 WHERE b.request_id = r.id;

DROP TABLE IF EXISTS publish_timestamp_backup_117;

COMMIT;
