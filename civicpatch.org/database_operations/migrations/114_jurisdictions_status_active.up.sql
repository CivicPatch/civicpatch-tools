-- jurisdictions.status: current -> active.
--
-- The column was already half-migrated: 9450 rows read `current` while 13 read `inactive`,
-- a pair that does not name one axis. Renaming the live value to `active` completes it, and
-- matches people.status (113), roles.status and role_aliases.status.
--
-- Meaning is unchanged: active = present in the synced jurisdictions.yml, inactive = removed
-- upstream (`deactivate_jurisdictions_not_in`). Status is derived from presence in the file,
-- never read out of it, so no source data or sync payload changes.
--
-- The CHECK arrives with the rename for the same reason as 113: nothing prevented the drift.
--
-- Idempotent: the UPDATE is a no-op once applied, and the default/constraint are guarded.
BEGIN;

UPDATE jurisdictions SET status = 'active' WHERE status = 'current';

ALTER TABLE jurisdictions ALTER COLUMN status SET DEFAULT 'active';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'jurisdictions_status_check'
    ) THEN
        ALTER TABLE jurisdictions
            ADD CONSTRAINT jurisdictions_status_check
            CHECK (status IN ('active', 'inactive'));
    END IF;
END $$;

COMMIT;
