BEGIN;

ALTER TABLE posts RENAME COLUMN meta_is_tracked TO _is_tracked;
ALTER TABLE posts RENAME COLUMN meta_headcount TO _headcount;

COMMIT;
