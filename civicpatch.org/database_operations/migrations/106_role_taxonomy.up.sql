BEGIN;

-- Role taxonomy, step 1 (plan: .scratch/2026-08-12-plan-role-taxonomy-model.md).
-- Splits `role_terms` into the concept (`roles`) and what each scope says about it
-- (`role_entries`), and folds `role_aliases` into an array on the entry.
--
-- Why the split: a `role_terms` row conflated the concept with its per-scope settings, so
-- "Council Member" global and "Council Member" in Texas were two unrelated rows, each
-- restating everything and each owning a separate alias set — `role_aliases.term_id`
-- pointed at a *scoped* row, not at the concept. That is what forced whole-entry
-- replacement in the merge (a city overriding one field had to restate role, aliases and
-- is_unique, then silently missed later global alias additions), and it left `posts` with
-- no stable thing to reference.
--
-- Why nullable columns on role_entries: NULL means "inherit from a broader scope", so a
-- city that renames its body writes one row with a label and nothing else. Inheritance
-- lives in the data model rather than in a merge function.
--
-- Why `kind` becomes `status`: the three exclusion rows are all real offices (city
-- attorney, city manager, city secretary) excluded because we collect elected officials
-- and these are appointed staff — a policy about scope, not a fact about vocabulary. Both
-- values are roles, so the axis is active/rejected. `candidate` is the third state a
-- boolean could not express, for triage of labels seen but not yet judged.
--
-- Idempotent: re-running finds the tables present and `role_terms` gone, so the backfill
-- is skipped and the drops are no-ops.

CREATE TABLE IF NOT EXISTS roles (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    key         text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT roles_key_uq UNIQUE (key)
);

CREATE TABLE IF NOT EXISTS role_entries (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id     uuid NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    scope       text,
    label       text,
    status      text,
    is_unique   boolean,
    priority    integer,
    aliases     text[] NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT role_entries_status_check
        CHECK (status IS NULL OR status IN ('active', 'candidate', 'rejected')),
    CONSTRAINT role_entries_scope_uq UNIQUE NULLS NOT DISTINCT (role_id, scope),
    -- Scoped rows may be sparse; the global row must be complete, so resolution always
    -- terminates with a renderable label and a status rather than needing a fallback.
    CONSTRAINT role_entries_global_complete
        CHECK (scope IS NOT NULL OR (label IS NOT NULL AND status IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS role_entries_role_idx ON role_entries (role_id);
CREATE INDEX IF NOT EXISTS role_entries_scope_idx ON role_entries (scope);
CREATE INDEX IF NOT EXISTS role_entries_aliases_idx ON role_entries USING GIN (aliases);

-- Backfill only while the old tables are still here. PL/pgSQL plans the inner statements
-- on execution, so referencing a dropped table inside the skipped branch is fine.
DO $$
BEGIN
    IF to_regclass('public.role_terms') IS NOT NULL THEN
        INSERT INTO roles (key)
        SELECT DISTINCT lower(regexp_replace(trim(value), '\s+', '_', 'g'))
        FROM role_terms
        ON CONFLICT ON CONSTRAINT roles_key_uq DO NOTHING;

        INSERT INTO role_entries (
            role_id, scope, label, status, is_unique, priority, aliases
        )
        SELECT r.id,
               t.jurisdiction_ocdid,
               t.value,
               CASE WHEN t.kind = 'exclusion' THEN 'rejected' ELSE 'active' END,
               t.is_unique,
               t.priority,
               COALESCE(
                   (SELECT array_agg(a.value ORDER BY a.value)
                    FROM role_aliases a
                    WHERE a.term_id = t.id AND a.disabled_at IS NULL),
                   '{}'
               )
        FROM role_terms t
        JOIN roles r
          ON r.key = lower(regexp_replace(trim(t.value), '\s+', '_', 'g'))
        ON CONFLICT ON CONSTRAINT role_entries_scope_uq DO NOTHING;
    END IF;
END $$;

DROP TABLE IF EXISTS role_aliases;
DROP TABLE IF EXISTS role_terms;

COMMIT;
