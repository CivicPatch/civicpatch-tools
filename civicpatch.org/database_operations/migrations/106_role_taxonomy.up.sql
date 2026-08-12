BEGIN;

-- Role taxonomy (plan: .scratch/2026-08-12-plan-role-taxonomy-model.md).
-- Replaces `role_terms` + `role_aliases` with a single `roles` table.
-- `role_aliases` folds into a text[] array; `kind` becomes `status`.
--
-- No `roles` table — `label` is the identity, `UNIQUE (label, scope)`.
-- Rename = UPDATE the row. Stable identity = the row's UUID.
--
-- Why nullable columns on roles: NULL means "inherit from a broader scope",
-- so a city that renames its body writes one row with a label and nothing else.
-- Inheritance lives in the data model rather than in a merge function.
--
-- Idempotent: re-running finds the table present and `role_terms` gone, so the
-- backfill is skipped and the drops are no-ops.

CREATE TABLE IF NOT EXISTS roles (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    label       text NOT NULL,
    scope       text,
    status      text,
    is_unique   boolean,
    priority    integer,
    aliases     text[] NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT roles_status_check
        CHECK (status IS NULL OR status IN ('active', 'candidate', 'rejected')),
    CONSTRAINT roles_label_scope_uq UNIQUE NULLS NOT DISTINCT (label, scope),
    -- Scoped rows may be sparse; the global row must be complete, so resolution
    -- always terminates with a renderable label and a status.
    CONSTRAINT roles_global_complete
        CHECK (scope IS NOT NULL OR (label IS NOT NULL AND status IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS roles_scope_idx ON roles (scope);
CREATE INDEX IF NOT EXISTS roles_aliases_idx ON roles USING GIN (aliases);

-- Backfill only while the old tables are still here.
DO $$
BEGIN
    IF to_regclass('public.role_terms') IS NOT NULL THEN
        INSERT INTO roles (
            label, scope, status, is_unique, priority, aliases
        )
        SELECT t.value,
               t.jurisdiction_ocdid,
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
        ON CONFLICT ON CONSTRAINT roles_label_scope_uq DO NOTHING;
    END IF;
END $$;

DROP TABLE IF EXISTS role_aliases;
DROP TABLE IF EXISTS role_terms;

COMMIT;