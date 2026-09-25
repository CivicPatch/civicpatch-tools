-- A membership row is a period held (step 15), bounded by opened_at and closed_at.
-- last_seen_at (the latest record confirming it) and created_at (when the row was inserted, which
-- a rebuilt table resets on every publish) describe neither end and nothing needs them.

BEGIN;

ALTER TABLE memberships DROP COLUMN IF EXISTS last_seen_at;
ALTER TABLE memberships DROP COLUMN IF EXISTS created_at;

COMMIT;
