BEGIN;

ALTER TABLE changesets DROP COLUMN IF EXISTS proposal_counts;
ALTER TABLE changeset_batches DROP COLUMN IF EXISTS rows_read;
ALTER TABLE changeset_batches DROP COLUMN IF EXISTS errors;

COMMIT;
