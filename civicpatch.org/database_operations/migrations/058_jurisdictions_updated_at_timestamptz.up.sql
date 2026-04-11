BEGIN;
ALTER TABLE jurisdictions
    ALTER COLUMN updated_at TYPE timestamptz USING updated_at AT TIME ZONE 'UTC';
COMMIT;
