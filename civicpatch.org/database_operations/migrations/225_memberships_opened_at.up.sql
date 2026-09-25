-- A membership is a stint (plan step 15): first_seen_at -> opened_at, so its boundaries read
-- opened / closed like the "open membership" the code already says. Pure rename.

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'memberships' AND column_name = 'first_seen_at') THEN
        ALTER TABLE memberships RENAME COLUMN first_seen_at TO opened_at;
    END IF;
END $$;

COMMIT;
