BEGIN;

-- pipeline_issues is now the generic issues worklist (informational events go to logs,
-- category dropped), so the "pipeline" prefix no longer fits. Indexes/constraints keep
-- their historical names — Postgres doesn't rename them with the table, and renaming them
-- is cosmetic.
ALTER TABLE pipeline_issues RENAME TO issues;

COMMIT;
