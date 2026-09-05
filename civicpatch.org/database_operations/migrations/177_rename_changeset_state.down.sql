BEGIN;

ALTER TABLE changesets RENAME COLUMN changeset_state TO state;

COMMIT;
