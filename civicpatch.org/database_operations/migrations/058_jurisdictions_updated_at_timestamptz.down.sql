BEGIN;
ALTER TABLE jurisdictions
    ALTER COLUMN updated_at TYPE timestamp USING updated_at AT TIME ZONE 'UTC';
COMMIT;
