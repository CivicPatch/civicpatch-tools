-- Exactly reverses 235.

BEGIN;

ALTER TABLE claims DROP CONSTRAINT IF EXISTS claims_changeset_id_fkey;
ALTER TABLE claims ADD CONSTRAINT claims_changeset_id_fkey
    FOREIGN KEY (changeset_id) REFERENCES changesets(id) ON DELETE SET NULL;

ALTER TABLE claims ALTER COLUMN changeset_id DROP NOT NULL;

COMMIT;
