BEGIN;

-- Reverses 108_role_labels_titlecase.up.sql: restores the original casing
-- from the migration 106 backfill. Since we don't store the original form,
-- the down migration is empty — re-apply 106's backfill logic if needed.
--
-- In practice this migration is only useful for reverting during development.
-- Production data is the canonical truth once 108 is applied.

COMMIT;