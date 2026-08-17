-- people.status: current/past -> active/inactive.
--
-- One vocabulary for "is this row live". `roles.status` already uses active/inactive, and
-- `role_aliases.status` uses active/candidate, so people was the odd one out — and `current`
-- collides with `jurisdictions.status`, which uses the same word for an unrelated idea.
--
-- Meaning is unchanged: active = named by the latest published roster, inactive = no longer
-- named (they left office). Inactive rows are kept, never deleted, so seat history survives.
--
-- The CHECK arrives with the rename because the column had none — nothing stopped a third
-- spelling appearing, which is how the vocabulary drifted in the first place.
--
-- Idempotent: the UPDATEs are no-ops once applied, and the default/constraint are guarded.
BEGIN;

UPDATE people SET status = 'active' WHERE status = 'current';
UPDATE people SET status = 'inactive' WHERE status = 'past';

ALTER TABLE people ALTER COLUMN status SET DEFAULT 'active';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'people_status_check'
    ) THEN
        ALTER TABLE people
            ADD CONSTRAINT people_status_check
            CHECK (status IN ('active', 'inactive'));
    END IF;
END $$;

COMMIT;
