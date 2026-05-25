BEGIN;

ALTER TABLE review_sessions RENAME COLUMN reviewed_request_ids TO reviewed_ocdids;

COMMIT;
