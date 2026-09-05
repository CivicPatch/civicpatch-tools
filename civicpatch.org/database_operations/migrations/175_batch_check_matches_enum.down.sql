BEGIN;

ALTER TABLE changeset_batches DROP CONSTRAINT IF EXISTS changeset_batches_kind_check;
ALTER TABLE changeset_batches ADD CONSTRAINT changeset_batches_kind_check
    CHECK (kind = ANY (ARRAY['sheet_import'::text, 'scrape'::text]));

ALTER TABLE changeset_batches DROP CONSTRAINT IF EXISTS changeset_batches_status_check;
ALTER TABLE changeset_batches ADD CONSTRAINT changeset_batches_status_check
    CHECK (status = ANY (ARRAY['running'::text, 'succeeded'::text, 'failed'::text, 'abandoned'::text]));

COMMIT;
