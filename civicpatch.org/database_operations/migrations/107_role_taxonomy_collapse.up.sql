BEGIN;

-- Collapse the two-table role taxonomy (roles + role_entries) into a single
-- `roles` table. Migration 106 created the two-table split; after review the
-- concept `roles` table was deemed unnecessary — `label` is the identity.
--
-- Drops the concept `roles` table, promotes `role_entries` to `roles`, drops
-- the `role_id` FK column. The `label` column already exists on `role_entries`
-- (backfilled from `role_terms.value` in migration 106), so no data movement.
--
-- Idempotent: guarded on `role_entries` still existing.

DO $$
BEGIN
    IF to_regclass('public.role_entries') IS NOT NULL THEN
        DROP TABLE IF EXISTS roles CASCADE;

        DROP INDEX IF EXISTS role_entries_role_idx;
        ALTER TABLE role_entries DROP COLUMN IF EXISTS role_id;

        ALTER TABLE role_entries DROP CONSTRAINT IF EXISTS role_entries_scope_uq;
        ALTER TABLE role_entries ADD CONSTRAINT roles_label_scope_uq
            UNIQUE NULLS NOT DISTINCT (label, scope);

        ALTER TABLE role_entries RENAME TO roles;

        ALTER INDEX IF EXISTS role_entries_pkey RENAME TO roles_pkey;
        ALTER INDEX IF EXISTS role_entries_scope_idx RENAME TO roles_scope_idx;
        ALTER INDEX IF EXISTS role_entries_aliases_idx RENAME TO roles_aliases_idx;
        ALTER TABLE roles RENAME CONSTRAINT role_entries_global_complete TO roles_global_complete;
        ALTER TABLE roles RENAME CONSTRAINT role_entries_status_check TO roles_status_check;
    END IF;
END $$;

COMMIT;