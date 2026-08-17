-- Re-stamp publish/dismiss timestamps from `change_logs` where 115 had to guess.
--
-- 115 backfilled `published_at` as COALESCE(pr.merged_at, pr.merge_enqueued_at, pr.updated_at)
-- and noted the caveat, but measured it against dev. Production says otherwise:
--
--   merged_at present        2742 of 3337 merged  (82%) — exact, GitHub's own merge time
--   merge_enqueued_at             2 of 3337              — the middle rung never fires
--   fell through to updated_at  595                      — "row last touched", not a publish time
--
-- Of those 595, 572 have a `merge_review` change_log, which is a real record of the review
-- landing rather than a proxy. Only 23 have no signal at all. Dismissals are worse off: no
-- closed row has `merged_at`, so all 298 took `updated_at`, while 74 have a `close_review` log.
--
-- Why change_logs is trustworthy here: where both exist, the two agree to within one second
-- (measured across 442 rows — `merged_at` is GitHub's clock at merge time, the change_log is
-- written when our side handled it). So mixing the sources introduces no skew.
--
-- Ordering is deliberate: `merged_at` stays authoritative and is never overwritten. This only
-- touches rows where 115 had nothing better than `updated_at`.
--
-- No schema change to `requests`, so DATABASE.md's diagram is unaffected — this rewrites values
-- only. The backup table below is migration scaffolding, dropped by the down migration.
--
-- WHY A BACKUP TABLE: the down migration cannot recompute 115's values. 115 wrote
-- `pr.updated_at` as it stood then, and `pull_requests.updated_at` keeps moving — pr_sync
-- rewrites it on every reconciliation. Recomputing would restore what the ladder yields today,
-- which is a different number. The prior values have to be kept to be given back.
--
-- Idempotent: the snapshot is ON CONFLICT DO NOTHING, so a re-run keeps the original values
-- rather than overwriting them with the corrected ones.
BEGIN;

-- min(): a republished request has several logs, and the first one is the publish that 115's
-- own COALESCE(published_at, now()) would have kept.
CREATE TEMP TABLE review_times ON COMMIT DROP AS
SELECT cl.request_id,
       min(cl.created_at) FILTER (WHERE cl.type = 'merge_review') AS published_at,
       min(cl.created_at) FILTER (WHERE cl.type = 'close_review') AS dismissed_at,
       (array_agg(cl.user_id ORDER BY cl.created_at)
        FILTER (WHERE cl.user_id IS NOT NULL))[1]                 AS user_id
FROM change_logs cl
WHERE cl.type IN ('merge_review', 'close_review')
GROUP BY cl.request_id;

CREATE TABLE IF NOT EXISTS publish_timestamp_backup_117 (
    request_id          uuid PRIMARY KEY REFERENCES requests(id) ON DELETE CASCADE,
    published_at        timestamptz,
    dismissed_at        timestamptz,
    resolved_by_user_id uuid
);

-- Snapshot before any write. The predicate is the union of the three updates below; a row
-- captured but ultimately unchanged restores to its own value, which is a no-op.
INSERT INTO publish_timestamp_backup_117 (request_id, published_at, dismissed_at, resolved_by_user_id)
SELECT r.id, r.published_at, r.dismissed_at, r.resolved_by_user_id
FROM requests r
JOIN review_times v ON v.request_id = r.id::text
WHERE (r.published_at IS NOT NULL AND v.published_at IS NOT NULL)
   OR (r.dismissed_at IS NOT NULL AND v.dismissed_at IS NOT NULL)
   OR (r.resolved_by_user_id IS NULL AND v.user_id IS NOT NULL)
ON CONFLICT (request_id) DO NOTHING;

UPDATE requests r
   SET published_at = v.published_at
  FROM review_times v, pull_requests pr
 WHERE v.request_id = r.id::text
   AND pr.request_id = r.id
   AND r.published_at IS NOT NULL
   AND pr.merged_at IS NULL          -- 115 had no exact time for this row
   AND v.published_at IS NOT NULL;

UPDATE requests r
   SET dismissed_at = v.dismissed_at
  FROM review_times v, pull_requests pr
 WHERE v.request_id = r.id::text
   AND pr.request_id = r.id
   AND r.dismissed_at IS NOT NULL
   AND v.dismissed_at IS NOT NULL;

-- 115 took `resolved_by_user_id` from the pull request, which is NULL wherever the merge was
-- reconciled by the hourly sync rather than driven by a person. The change_log knows who acted.
UPDATE requests r
   SET resolved_by_user_id = v.user_id
  FROM review_times v
 WHERE v.request_id = r.id::text
   AND r.resolved_by_user_id IS NULL
   AND v.user_id IS NOT NULL;

COMMIT;
