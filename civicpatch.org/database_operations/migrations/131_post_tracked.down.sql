BEGIN;

ALTER TABLE posts RENAME COLUMN _headcount TO headcount;
ALTER TABLE posts DROP COLUMN _is_tracked;

COMMIT;
