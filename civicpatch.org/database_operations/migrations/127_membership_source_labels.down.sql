BEGIN;

ALTER TABLE memberships DROP COLUMN source_labels;

COMMIT;
