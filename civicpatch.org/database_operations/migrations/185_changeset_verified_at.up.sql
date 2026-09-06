-- When a person stood behind this changeset, as distinct from when it was published.
--
-- Nothing has ever auto-published, so every existing published row was attended by someone and
-- backfills to its own `published_at`. Once the cadence flush lands, a changeset can publish
-- with nobody having looked — `published_at` set, `verified_at` NULL — and the two stop being
-- the same question.

BEGIN;

ALTER TABLE changesets
    ADD COLUMN IF NOT EXISTS verified_at timestamptz;

UPDATE changesets
   SET verified_at = published_at
 WHERE published_at IS NOT NULL
   AND verified_at IS NULL;

COMMIT;
