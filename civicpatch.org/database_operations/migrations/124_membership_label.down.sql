-- Reverses 124. Any label a person set goes with it; nothing derived is lost, since
-- `designations` and `unmatched_text` are untouched.

BEGIN;

ALTER TABLE memberships
    DROP COLUMN IF EXISTS label;

COMMIT;
