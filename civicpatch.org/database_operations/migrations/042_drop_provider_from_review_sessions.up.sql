BEGIN;

ALTER TABLE review_sessions DROP COLUMN provider;
ALTER TABLE review_sessions DROP COLUMN provider_user_id;

COMMIT;
