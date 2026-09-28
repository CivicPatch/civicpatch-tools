-- Every claim names the act that filed it (234 attached the old ones; every writer passes one), so
-- rollback reaches all of them and the loader needs no rule for a claim without one. A changeset
-- owns its claims as it owns its source records: deleting it deletes them.

BEGIN;

ALTER TABLE claims ALTER COLUMN changeset_id SET NOT NULL;

ALTER TABLE claims DROP CONSTRAINT IF EXISTS claims_changeset_id_fkey;
ALTER TABLE claims ADD CONSTRAINT claims_changeset_id_fkey
    FOREIGN KEY (changeset_id) REFERENCES changesets(id) ON DELETE CASCADE;

COMMIT;
