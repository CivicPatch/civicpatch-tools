BEGIN;

ALTER TABLE memberships ADD COLUMN IF NOT EXISTS source_labels text[] NOT NULL DEFAULT '{}';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'memberships' AND column_name = 'sources'
    ) THEN
        UPDATE memberships SET source_labels = membership_source_labels(sources);
        ALTER TABLE memberships DROP COLUMN IF EXISTS sources;
    END IF;
END
$$;

DROP FUNCTION IF EXISTS membership_source_labels(jsonb);

COMMIT;
