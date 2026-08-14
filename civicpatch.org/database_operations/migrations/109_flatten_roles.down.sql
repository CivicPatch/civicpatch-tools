BEGIN;

-- Reverses 109_flatten_roles.up.sql: restores the uuid primary key, the `scope`
-- hierarchy, and the nullability that expressed inheritance.
--
-- Not fully reversible, in three ways, none worth engineering around:
--   * The scoped row the up migration deleted is gone. It was test data
--     (`Blah` at Michigan state scope).
--   * Restored `id` values are freshly generated, not the originals. Nothing
--     references `roles` yet, so no FK is stranded by that.
--   * `inactive` rows are DELETEd. Pre-109 the status does not exist, and the
--     user action that sets it — removing a role — was a hard DELETE back then,
--     so deleting is the faithful reverse. (`excluded` -> `rejected` is a pure
--     rename and does round-trip.)
-- Every surviving row returns at global scope (scope NULL), which is where all
-- 24 of them already were.
--
-- Idempotent: guarded on the `scope` column still being absent.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'roles' AND column_name = 'scope'
    ) THEN
        DROP INDEX IF EXISTS roles_label_lower_uq;

        ALTER TABLE roles DROP CONSTRAINT roles_pkey;
        ALTER TABLE roles DROP COLUMN id;
        ALTER TABLE roles ADD COLUMN id UUID NOT NULL DEFAULT gen_random_uuid();
        ALTER TABLE roles ADD CONSTRAINT roles_pkey PRIMARY KEY (id);

        ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_status_check;
        DELETE FROM roles WHERE status = 'inactive';
        UPDATE roles SET status = 'rejected' WHERE status = 'excluded';
        ALTER TABLE roles ADD CONSTRAINT roles_status_check
            CHECK (status IS NULL OR status IN ('active', 'candidate', 'rejected'));

        ALTER TABLE roles ALTER COLUMN is_unique DROP NOT NULL;
        ALTER TABLE roles ALTER COLUMN is_unique DROP DEFAULT;
        ALTER TABLE roles ALTER COLUMN status DROP NOT NULL;
        ALTER TABLE roles ALTER COLUMN label DROP NOT NULL;

        ALTER TABLE roles ADD COLUMN scope TEXT;
        CREATE INDEX roles_scope_idx ON roles (scope);
        ALTER TABLE roles ADD CONSTRAINT roles_label_scope_uq
            UNIQUE NULLS NOT DISTINCT (label, scope);
        ALTER TABLE roles ADD CONSTRAINT roles_global_complete
            CHECK (scope IS NOT NULL OR (label IS NOT NULL AND status IS NOT NULL));
    END IF;
END $$;

COMMIT;
