-- Exactly reverses the up: the rows go back before the new types are dropped.

BEGIN;

INSERT INTO change_log_types (type) VALUES ('merge_review'), ('close_review')
    ON CONFLICT (type) DO NOTHING;

UPDATE change_logs SET type = 'merge_review' WHERE type = 'publish_review';
UPDATE change_logs SET type = 'close_review' WHERE type = 'dismiss_review';

DELETE FROM change_log_types WHERE type IN ('publish_review', 'dismiss_review');

COMMIT;
