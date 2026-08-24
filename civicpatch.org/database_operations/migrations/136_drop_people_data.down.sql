BEGIN;

ALTER TABLE people ALTER COLUMN name DROP NOT NULL;

-- Restored empty: the rows it held are reproducible from the columns via `PERSON_JSON`, and
-- writing a backfill here would make the down migration depend on that expression staying put.
ALTER TABLE people ADD COLUMN data jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMIT;
