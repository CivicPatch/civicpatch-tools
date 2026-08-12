BEGIN;

-- Reverses 106_role_taxonomy.up.sql: rebuilds `role_terms` + `role_aliases` from
-- `roles` + `role_entries`, then drops the new pair.
--
-- Two things do not round-trip, both because the up migration dropped information that
-- was empty at the time:
--
--   * `status = 'candidate'` collapses to `kind = 'canonical'`. `kind` has two values and
--     `status` has three, so a row marked candidate after the up ran cannot be
--     represented. Rejected still maps to exclusion.
--   * `role_aliases.source` comes back as 'curated' with `confidence` and `disabled_at`
--     null. All 116 rows were exactly that when the up ran (0 non-null confidence,
--     0 disabled, single-valued source), which is why the columns were dropped.
--
-- Scoped entries may leave `label` null (it inherits), but `role_terms.value` is NOT
-- NULL, so those fall back to the concept key.
--
-- Idempotent: re-running finds the old tables present and `role_entries` gone, so the
-- backfill is skipped and the drops are no-ops.

CREATE TABLE IF NOT EXISTS role_terms (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    value               text NOT NULL,
    kind                text NOT NULL,
    jurisdiction_ocdid  text,
    display_name        text,
    is_unique           boolean NOT NULL DEFAULT false,
    priority            integer NOT NULL DEFAULT 0,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT role_terms_kind_check CHECK (kind IN ('canonical', 'exclusion')),
    CONSTRAINT role_terms_scope_uq UNIQUE NULLS NOT DISTINCT (value, jurisdiction_ocdid)
);

CREATE TABLE IF NOT EXISTS role_aliases (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    term_id      uuid NOT NULL REFERENCES role_terms(id) ON DELETE CASCADE,
    value        text NOT NULL,
    source       text NOT NULL,
    confidence   real,
    disabled_at  timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT role_aliases_source_check
        CHECK (source IN ('curated', 'confirmed', 'learned'))
);

CREATE UNIQUE INDEX IF NOT EXISTS role_aliases_active_uq
    ON role_aliases (term_id, value) WHERE disabled_at IS NULL;
CREATE INDEX IF NOT EXISTS role_aliases_value_idx
    ON role_aliases (value) WHERE disabled_at IS NULL;

DO $$
BEGIN
    IF to_regclass('public.role_entries') IS NOT NULL THEN
        INSERT INTO role_terms (
            value, kind, jurisdiction_ocdid, display_name, is_unique, priority
        )
        SELECT COALESCE(e.label, r.key),
               CASE WHEN e.status = 'rejected' THEN 'exclusion' ELSE 'canonical' END,
               e.scope,
               COALESCE(e.label, r.key),
               COALESCE(e.is_unique, false),
               COALESCE(e.priority, 0)
        FROM role_entries e
        JOIN roles r ON r.id = e.role_id
        ON CONFLICT ON CONSTRAINT role_terms_scope_uq DO NOTHING;

        INSERT INTO role_aliases (term_id, value, source)
        SELECT t.id, alias, 'curated'
        FROM role_entries e
        JOIN roles r ON r.id = e.role_id
        JOIN role_terms t
          ON t.value = COALESCE(e.label, r.key)
         AND t.jurisdiction_ocdid IS NOT DISTINCT FROM e.scope
        CROSS JOIN LATERAL unnest(e.aliases) AS alias
        ON CONFLICT DO NOTHING;
    END IF;
END $$;

DROP TABLE IF EXISTS role_entries;
DROP TABLE IF EXISTS roles;

COMMIT;
