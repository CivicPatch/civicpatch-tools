BEGIN;
ALTER TABLE notes
    DROP CONSTRAINT notes_user_id_fkey,
    ALTER COLUMN user_id TYPE text USING user_id::text,
    ALTER COLUMN user_id SET NOT NULL;
COMMIT;
