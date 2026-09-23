BEGIN;

ALTER TABLE assertions DROP CONSTRAINT IF EXISTS assertions_sources_nonempty;
ALTER TABLE assertions ALTER COLUMN sources DROP NOT NULL;

COMMIT;
