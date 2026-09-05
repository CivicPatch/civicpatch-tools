BEGIN;

ALTER TABLE changesets DROP COLUMN IF EXISTS changeset_state;
ALTER TABLE changesets ADD COLUMN IF NOT EXISTS changeset_state text
    GENERATED ALWAYS AS (
        CASE
            WHEN published_at IS NOT NULL THEN 'published'
            WHEN dismissed_at IS NOT NULL THEN 'dismissed'
            ELSE 'ready'
        END
    ) STORED;

COMMIT;
