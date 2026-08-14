BEGIN;

-- Reverses 110_role_aliases.up.sql: folds aliases back into `roles.aliases`.
--
-- Not fully reversible: `candidate` aliases are DROPPED. The array has nowhere
-- to record that an alias is unapproved, and restoring one as an ordinary
-- element would make it match — the exact thing approval exists to prevent.
--
-- Idempotent: guarded on `roles.aliases` still being absent.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'roles' AND column_name = 'aliases'
    ) THEN
        ALTER TABLE roles ADD COLUMN aliases TEXT[] NOT NULL DEFAULT '{}';

        UPDATE roles r
           SET aliases = COALESCE(
                   (SELECT array_agg(a.label ORDER BY a.label)
                      FROM role_aliases a
                     WHERE a.role_id = r.id AND a.status = 'active'),
                   '{}'
               );

        CREATE INDEX roles_aliases_idx ON roles USING GIN (aliases);

        DROP TABLE role_aliases;
    END IF;
END $$;

COMMIT;
