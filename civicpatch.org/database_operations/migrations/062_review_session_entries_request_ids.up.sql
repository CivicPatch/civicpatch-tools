BEGIN;

ALTER TABLE review_session_entries
  ADD COLUMN request_ids TEXT[],
  ADD COLUMN entry_kind TEXT NOT NULL DEFAULT 'jurisdiction';

UPDATE review_session_entries SET request_ids = ARRAY[request_id];

ALTER TABLE review_session_entries
  ALTER COLUMN request_ids SET NOT NULL,
  DROP COLUMN request_id;

COMMIT;
