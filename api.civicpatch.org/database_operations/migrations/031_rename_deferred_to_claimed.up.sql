BEGIN;

UPDATE review_session_entries SET status = 'claimed' WHERE status = 'deferred';

ALTER TABLE review_session_entries ALTER COLUMN status SET DEFAULT 'claimed';

COMMIT;
