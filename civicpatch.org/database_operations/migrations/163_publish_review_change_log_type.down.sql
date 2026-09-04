-- Exactly reverses the up: the rows go back to `merge_review` before the type is dropped.

BEGIN;

INSERT INTO change_log_types (type) VALUES ('merge_review')
    ON CONFLICT (type) DO NOTHING;

UPDATE change_logs SET type = 'merge_review' WHERE type = 'publish_review';

DELETE FROM change_log_types WHERE type = 'publish_review';

COMMIT;
