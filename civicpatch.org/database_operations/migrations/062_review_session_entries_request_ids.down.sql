BEGIN;

ALTER TABLE review_session_entries ADD COLUMN request_id TEXT;

UPDATE review_session_entries SET request_id = request_ids[1];

ALTER TABLE review_session_entries
  ALTER COLUMN request_id SET NOT NULL,
  DROP COLUMN request_ids,
  DROP COLUMN entry_kind;

COMMIT;
