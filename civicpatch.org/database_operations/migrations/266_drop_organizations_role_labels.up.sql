-- A post's name and an organization's roles come from its place's law, else the config form
-- (core/organization_derivation.py); the copy stored here was filled once and went stale.

BEGIN;

ALTER TABLE organizations DROP COLUMN IF EXISTS extras_role_labels;

COMMIT;
