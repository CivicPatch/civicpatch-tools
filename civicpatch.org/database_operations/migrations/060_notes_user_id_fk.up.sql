BEGIN;
ALTER TABLE notes
    ALTER COLUMN user_id TYPE uuid USING user_id::uuid,
    ADD CONSTRAINT notes_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
COMMIT;
