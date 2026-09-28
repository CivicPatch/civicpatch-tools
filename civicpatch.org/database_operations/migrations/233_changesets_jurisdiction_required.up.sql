-- Every changeset belongs to one jurisdiction: every insert names it, and prod held none without
-- one (2026-09-27), so the loader's branch for a changeset with no jurisdiction can go.

BEGIN;

ALTER TABLE changesets ALTER COLUMN jurisdiction_ocdid SET NOT NULL;

COMMIT;
