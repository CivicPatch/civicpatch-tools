BEGIN;

ALTER INDEX memberships_meta_unmatched_text_idx RENAME TO memberships_unmatched_text_idx;
ALTER TABLE memberships RENAME COLUMN meta_unmatched_text TO unmatched_text;

COMMIT;
