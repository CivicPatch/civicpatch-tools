BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'state_settings' AND column_name = 'cadence_anchor'
    ) THEN
        ALTER TABLE state_settings RENAME COLUMN cadence_anchor TO cadence_start;
    END IF;
END $$;

COMMIT;
