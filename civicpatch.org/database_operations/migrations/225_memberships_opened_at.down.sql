-- Exactly reverses 225.

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'memberships' AND column_name = 'opened_at') THEN
        ALTER TABLE memberships RENAME COLUMN opened_at TO first_seen_at;
    END IF;
END $$;

COMMIT;
