BEGIN;

-- What an import found wrong, kept with the batch so it outlives the response that carried it.
ALTER TABLE changeset_batches ADD COLUMN IF NOT EXISTS errors jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE changeset_batches ADD COLUMN IF NOT EXISTS rows_read int;

-- What a sheet import proposed, counted when it was made, so the batch page need not rebuild
-- every locality's roster to show "2 added, 1 absent". NULL for every other changeset.
ALTER TABLE changesets ADD COLUMN IF NOT EXISTS proposal_counts jsonb;

-- Older batches can't be counted in SQL: expire their undecided imports and drop the batches.
-- Every import from here on sets `rows_read`, so a re-run touches nothing.
UPDATE changesets
   SET dismissed_at = now(), dismissed_reason = 'expired'
 WHERE published_at IS NULL
   AND dismissed_at IS NULL
   AND batch_id IN (SELECT id FROM changeset_batches WHERE rows_read IS NULL);

UPDATE changesets
   SET batch_id = NULL
 WHERE batch_id IN (SELECT id FROM changeset_batches WHERE rows_read IS NULL);

DELETE FROM changeset_batches WHERE rows_read IS NULL;

COMMIT;
