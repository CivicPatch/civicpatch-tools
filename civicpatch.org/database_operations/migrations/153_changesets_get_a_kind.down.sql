-- Reverses 153. Lossy in one direction that cannot be helped, and it is worth naming.
--
-- The up migration replaced four distinct values with what the old column could express, which
-- for the three people producers is the single value `people`. Rolling back therefore collapses
-- `scrape`, `sheet_import` and `people_edit` back into one — the very conflation 153 exists to
-- remove. Nothing is *lost* that was not already unrecoverable before 153: the conjunction of
-- `status` and `batch_id` still distinguishes them, which is how the up migration derived them
-- in the first place.
--
-- The `state_scrape` spelling comes back on `changeset_batches` so the CHECK matches what 149
-- created.
BEGIN;

ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_scrape_has_a_run;
ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_kind_check;

UPDATE changesets
   SET kind = CASE
       WHEN kind = 'jurisdiction_edit' THEN 'jurisdiction_manual_edit'
       ELSE 'people'
   END;

-- 141's shape: NOT NULL with a default of 'scrape'.
ALTER TABLE changesets ALTER COLUMN kind SET DEFAULT 'scrape';

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'changesets'
                 AND column_name = 'kind') THEN
        ALTER TABLE changesets RENAME COLUMN kind TO request_type;
    END IF;
END $$;

ALTER TABLE changeset_batches DROP CONSTRAINT IF EXISTS changeset_batches_kind_check;
UPDATE changeset_batches SET kind = 'state_scrape' WHERE kind = 'scrape';
ALTER TABLE changeset_batches ADD CONSTRAINT changeset_batches_kind_check
    CHECK (kind IN ('sheet_import', 'state_scrape'));

COMMIT;
