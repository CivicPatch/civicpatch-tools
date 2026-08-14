BEGIN;

-- Flatten the role taxonomy: drop the global/state/locality `scope` hierarchy
-- in favour of a single flat list, and key the table on a readable `slug`.
-- See .scratch/2026-08-12-plan-flat-roles.md.
--
-- Why flat: `scope` carried 24 global rows plus 1 scoped test row, while
-- costing the promotion trap. Promoting a role from locality to global is
-- DELETE + INSERT, which mints a new key — and that would break the
-- `posts.role_id` FK Phase 2 adds. Flat has no ladder, so no promotion and no
-- churn.
--
-- Why `id` becomes a slug: the uuid's only job was surviving a rename, and a
-- slug derived once at creation already does that. Done now because nothing FKs
-- to `roles` yet, so it is the cheapest it will ever be. See DATABASE.md for
-- what the name costs and why Phase 2's FK wants ON UPDATE CASCADE.
--
-- Also tightens what the hierarchy had loosened: `label`, `status` and
-- `is_unique` were nullable only to mean "inherit from the scope above", which
-- means nothing now. 0 of 25 rows used it. `priority` stays nullable —
-- `ORDER BY priority NULLS LAST` treats NULL as a real state (unranked).
--
-- Idempotent: guarded on the `scope` column still existing.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'roles' AND column_name = 'scope'
    ) THEN
        -- The only scoped row is `Blah`, test data from building the config
        -- editor. Deleted before SET NOT NULL because a scoped row is precisely
        -- what `roles_global_complete` allowed to carry NULLs.
        DELETE FROM roles WHERE scope IS NOT NULL;

        DROP INDEX IF EXISTS roles_scope_idx;
        ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_global_complete;
        ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_label_scope_uq;
        ALTER TABLE roles DROP COLUMN scope;

        ALTER TABLE roles ALTER COLUMN label SET NOT NULL;
        ALTER TABLE roles ALTER COLUMN status SET NOT NULL;

        UPDATE roles SET is_unique = false WHERE is_unique IS NULL;
        ALTER TABLE roles ALTER COLUMN is_unique SET DEFAULT false;
        ALTER TABLE roles ALTER COLUMN is_unique SET NOT NULL;

        -- Each status is a distinct matcher behaviour: active matches,
        -- candidate matches and flags for triage, excluded matches so the label
        -- can be knowingly dropped, inactive is not matched at all.
        -- `rejected` -> `excluded` is a rename: it aligns with the
        -- `exclude_role`/`include_role` change_log types, which are permanent
        -- (existing change_logs rows FK to them). `inactive` is new — it is what
        -- removal sets, replacing the pre-109 hard DELETE.
        -- The `status IS NULL` branch goes with the NOT NULL above.
        -- Constraint dropped first: the old one forbids 'excluded'.
        ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_status_check;
        UPDATE roles SET status = 'excluded' WHERE status = 'rejected';
        ALTER TABLE roles ADD CONSTRAINT roles_status_check
            CHECK (status IN ('active', 'candidate', 'excluded', 'inactive'));

        -- Dropped and re-added rather than retyped: there is no uuid -> slug
        -- cast, the value is derived from `label`. `database.roles.slugify_label`
        -- must reproduce the expression below exactly.
        ALTER TABLE roles DROP CONSTRAINT roles_pkey;
        ALTER TABLE roles DROP COLUMN id;

        ALTER TABLE roles ADD COLUMN id TEXT;
        UPDATE roles
           SET id = trim(both '-' from lower(regexp_replace(label, '[^a-zA-Z0-9]+', '-', 'g')));
        ALTER TABLE roles ALTER COLUMN id SET NOT NULL;
        ALTER TABLE roles ADD CONSTRAINT roles_pkey PRIMARY KEY (id);

        -- NOT NULL does not cover ''. A label of pure punctuation slugs to the
        -- empty string, which would insert silently as published identity.
        ALTER TABLE roles ADD CONSTRAINT roles_id_not_empty CHECK (id <> '');

        -- Case-insensitive, unlike the constraint it replaces. `role_config.py`
        -- already dedupes on `label.lower()`, so a case-differing pair was one
        -- entry in the API response and two rows in the table, with the second
        -- unreachable. Zero such pairs exist today, so this is free to add now
        -- and awkward later. Expression index, not a table constraint.
        CREATE UNIQUE INDEX roles_label_lower_uq ON roles (lower(label));
    END IF;
END $$;

COMMIT;
