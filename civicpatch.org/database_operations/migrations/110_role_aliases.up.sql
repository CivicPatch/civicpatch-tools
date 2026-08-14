BEGIN;

-- Aliases move from `roles.aliases text[]` back into their own table, reversing
-- the fold migration 106 did. The array cannot express two things:
--   * An approval lifecycle. An alias must not match until a maintainer
--     approves it, and per-alias state has nowhere to live in an array.
--   * Uniqueness across roles. Nothing stopped one string being an alias of two
--     roles, which makes the matcher's answer arbitrary. Free to enforce today:
--     all aliases are already distinct case-insensitively (109 dev, 125 test).
--
-- `status` reuses the `roles` vocabulary rather than inventing a second one:
-- active matches, candidate does not. 095's `source`/`confidence` columns are
-- deliberately not restored — nothing auto-mints aliases, so they would be
-- speculative.
--
-- Idempotent: guarded on `roles.aliases` still existing.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'roles' AND column_name = 'aliases'
    ) THEN
        CREATE TABLE role_aliases (
            id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            -- ON UPDATE CASCADE because roles.id is a derived slug and so can be
            -- wrong; correcting it should stay one statement.
            role_id    TEXT NOT NULL REFERENCES roles(id) ON UPDATE CASCADE ON DELETE CASCADE,
            label      TEXT NOT NULL,
            status     TEXT NOT NULL DEFAULT 'candidate'
                       CHECK (status IN ('active', 'candidate')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        -- Everything already in the array was typed by a maintainer, so it is
        -- approved by definition.
        INSERT INTO role_aliases (role_id, label, status)
        SELECT id, unnest(aliases), 'active' FROM roles;

        CREATE UNIQUE INDEX role_aliases_label_lower_uq ON role_aliases (lower(label));
        CREATE INDEX role_aliases_role_id_idx ON role_aliases (role_id);

        DROP INDEX IF EXISTS roles_aliases_idx;
        ALTER TABLE roles DROP COLUMN aliases;
    END IF;
END $$;

COMMIT;
