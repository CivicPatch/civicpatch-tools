-- Exactly reverses the up.

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'changesets'
           AND column_name = 'updated_at'
    ) THEN
        ALTER TABLE changesets RENAME COLUMN updated_at TO sourced_at;
    END IF;
END $$;

COMMIT;
