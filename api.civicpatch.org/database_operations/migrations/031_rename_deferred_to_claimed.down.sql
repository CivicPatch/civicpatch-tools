BEGIN;

ALTER TABLE review_session_entries ALTER COLUMN status SET DEFAULT 'deferred';

UPDATE review_session_entries SET status = 'deferred' WHERE status = 'claimed';

COMMIT;
