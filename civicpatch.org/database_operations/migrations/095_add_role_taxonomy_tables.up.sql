BEGIN;

-- Role taxonomy moves from open-data config.yml into the DB (issue #2375, Phase 1).
-- Scope is a single hierarchical jurisdiction_ocdid: NULL = global, a state ocdid = state
-- tier, an exact place ocdid = local tier. County is not a scoping tier. Not FK'd to
-- jurisdictions (state/global ocdids aren't rows there; mirrors change_logs.jurisdiction_ocdid).
-- All three tables soft-disable via disabled_at (uniform; append-only invariant).
-- Unique constraints are active-only so a disabled row never blocks re-creating the same key.

CREATE TABLE roles (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    value              TEXT NOT NULL,                -- canonical role name (e.g. "Council Member")
    display_name       TEXT NOT NULL,
    jurisdiction_ocdid TEXT,                          -- NULL = global; state ocdid = state; place ocdid = local
    is_unique          BOOLEAN NOT NULL DEFAULT FALSE,
    priority           INTEGER NOT NULL DEFAULT 0,    -- preserves config.yml list order
    disabled_at        TIMESTAMPTZ,                   -- soft-disable: NULL = active
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX roles_scope_active_uq
    ON roles (value, jurisdiction_ocdid) NULLS NOT DISTINCT WHERE disabled_at IS NULL;

CREATE TABLE role_aliases (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id     UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    value       TEXT NOT NULL,                        -- input form that maps to the canonical role
    source      TEXT NOT NULL CHECK (source IN ('curated', 'confirmed', 'learned')),
    confidence  REAL,                                 -- only meaningful for source='learned'
    disabled_at TIMESTAMPTZ,                           -- append-only: NULL = active
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX role_aliases_active_uq ON role_aliases (role_id, value) WHERE disabled_at IS NULL;
CREATE INDEX role_aliases_value_idx ON role_aliases (value) WHERE disabled_at IS NULL;

CREATE TABLE role_exclusions (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    value              TEXT NOT NULL,                 -- input string to suppress (e.g. "city hall")
    jurisdiction_ocdid TEXT,                          -- NULL = global; same scoping as roles
    source             TEXT NOT NULL CHECK (source IN ('curated', 'confirmed')),
    disabled_at        TIMESTAMPTZ,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX role_exclusions_active_uq
    ON role_exclusions (value, jurisdiction_ocdid) NULLS NOT DISTINCT WHERE disabled_at IS NULL;
CREATE INDEX role_exclusions_value_idx ON role_exclusions (value) WHERE disabled_at IS NULL;

ALTER TABLE change_logs DROP CONSTRAINT IF EXISTS change_logs_type_valid;
ALTER TABLE change_logs ADD CONSTRAINT change_logs_type_valid CHECK (type IN (
    'merge_review', 'close_review',
    'add_person', 'edit_person', 'delete_person', 'edit_jurisdiction',
    'add_role', 'edit_role', 'disable_role',
    'add_role_alias', 'disable_role_alias',
    'add_role_exclusion', 'disable_role_exclusion'
));

COMMIT;