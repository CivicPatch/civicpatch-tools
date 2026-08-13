BEGIN;

-- Reverses 107_role_taxonomy_collapse.up.sql: splits `roles` back into
-- `roles` (concept table) + `role_entries` (scoped entries).
--
-- The concept `roles` table is rebuilt with a `key` slugified from `label`,
-- matching the slugify expression in migration 106
-- (`lower(regexp_replace(trim(label), '\s+', '_', 'g'))`).
--
-- Idempotent: guarded on `role_entries` NOT existing and the current `roles`
-- table having the `roles_global_complete` check (the single-table schema).

DO $$
BEGIN
    IF to_regclass('public.role_entries') IS NULL
       AND EXISTS (SELECT 1 FROM information_schema.table_constraints
                   WHERE table_name = 'roles'
                     AND constraint_name = 'roles_global_complete')
    THEN
        -- Build the concept table under a temp name (the real name is taken
        -- by the single-table schema right now).
        CREATE TABLE roles_concept (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            key         text NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT roles_concept_key_uq UNIQUE (key)
        );

        INSERT INTO roles_concept (key)
        SELECT DISTINCT lower(regexp_replace(trim(label), '\s+', '_', 'g'))
        FROM roles
        ON CONFLICT ON CONSTRAINT roles_concept_key_uq DO NOTHING;

        -- Swap names: current single-table roles -> role_entries, concept -> roles.
        ALTER TABLE roles RENAME TO role_entries;
        ALTER TABLE role_entries DROP CONSTRAINT IF EXISTS roles_label_scope_uq;
        ALTER TABLE role_entries DROP CONSTRAINT IF EXISTS roles_global_complete;
        ALTER TABLE role_entries DROP CONSTRAINT IF EXISTS roles_status_check;
        ALTER TABLE roles_concept RENAME TO roles;

        ALTER INDEX IF EXISTS roles_pkey RENAME TO role_entries_pkey;
        ALTER INDEX IF EXISTS roles_scope_idx RENAME TO role_entries_scope_idx;
        ALTER INDEX IF EXISTS roles_aliases_idx RENAME TO role_entries_aliases_idx;

        -- Re-add the FK column and backfill from the concept key.
        ALTER TABLE role_entries ADD COLUMN IF NOT EXISTS role_id uuid;
        UPDATE role_entries e SET role_id = r.id
        FROM roles r
        WHERE r.key = lower(regexp_replace(trim(e.label), '\s+', '_', 'g'));
        ALTER TABLE role_entries ALTER COLUMN role_id SET NOT NULL;

        ALTER TABLE role_entries ADD CONSTRAINT role_entries_role_id_fkey
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE;
        CREATE INDEX IF NOT EXISTS role_entries_role_idx ON role_entries (role_id);

        ALTER TABLE role_entries ADD CONSTRAINT role_entries_scope_uq
            UNIQUE NULLS NOT DISTINCT (role_id, scope);
        ALTER TABLE role_entries ADD CONSTRAINT role_entries_global_complete
            CHECK (scope IS NOT NULL OR (label IS NOT NULL AND status IS NOT NULL));
        ALTER TABLE role_entries ADD CONSTRAINT role_entries_status_check
            CHECK (status IS NULL OR status IN ('active', 'candidate', 'rejected'));
    END IF;
END $$;

COMMIT;