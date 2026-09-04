-- Restores the columns and copies the values back from `pipeline_runs`, which is where 169 put
-- them. A run with no changeset has nothing to copy back — it never had a changeset row.

BEGIN;

ALTER TABLE changesets DROP COLUMN IF EXISTS state;

ALTER TABLE changesets
    ADD COLUMN IF NOT EXISTS status text,
    ADD COLUMN IF NOT EXISTS progress integer,
    ADD COLUMN IF NOT EXISTS arguments_json jsonb NOT NULL DEFAULT '{}'::jsonb;

UPDATE changesets c
   SET status = r.status, progress = r.progress, arguments_json = r.arguments_json
  FROM pipeline_runs r
 WHERE r.changeset_id = c.id;

ALTER TABLE changesets
    ADD COLUMN IF NOT EXISTS state text GENERATED ALWAYS AS (
        CASE
            WHEN published_at IS NOT NULL THEN 'published'
            WHEN dismissed_at IS NOT NULL THEN 'dismissed'
            WHEN status = ANY (ARRAY['ERROR', 'CANCELLED']) THEN 'failed'
            WHEN status IS NULL OR status = ANY (ARRAY['SUCCESS', 'RESOLVED']) THEN 'ready'
            ELSE 'running'
        END
    ) STORED;

ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_scrape_has_a_run;
ALTER TABLE changesets ADD CONSTRAINT changesets_scrape_has_a_run
    CHECK ((kind = 'scrape') = (status IS NOT NULL));

COMMIT;
