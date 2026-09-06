-- `cadence_start` was a misleading name for what the column does.
--
-- It becomes `ScheduleIntervalSpec(offset=)`, and a Temporal interval schedule fires at every
-- `epoch + n*every + offset` — it does not wait for a date. So a "start" of 2026-12-01 on a
-- 30-day cadence fires on 2026-10-02, the boundary whose phase matches, and every 30 days from
-- there. December is on the cycle; it is not where the cycle begins.
--
-- The behaviour is wanted — it is how fifty states are staggered instead of all firing at one
-- midnight. Only the name was wrong, and a form field labelled "start date" that does not delay
-- the first run misleads whoever fills it in. Renamed before any UI was built against it.
--
-- Wrapped in a DO block because ALTER TABLE ... RENAME COLUMN has no IF EXISTS, and every DDL
-- statement here has to be re-runnable.

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'state_settings' AND column_name = 'cadence_start'
    ) THEN
        ALTER TABLE state_settings RENAME COLUMN cadence_start TO cadence_anchor;
    END IF;
END $$;

COMMIT;
