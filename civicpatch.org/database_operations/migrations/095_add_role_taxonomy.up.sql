BEGIN;

-- Role taxonomy moves from open-data config.yml into the DB (issue #2375, Phase 1).
--
-- Unified design: role_terms holds BOTH canonical roles AND exclusion patterns,
-- distinguished by kind. Aliases attach to a term regardless of kind, so
-- "excluding" a role is an UPDATE of kind (aliases come along automatically).
--
-- Scope is a single hierarchical jurisdiction_ocdid: NULL = global, a state
-- ocdid = state tier, an exact place ocdid = local tier. County is not a
-- scoping tier. Not FK'd to jurisdictions (state/global ocdids aren't rows
-- there; mirrors change_logs.jurisdiction_ocdid).

CREATE TABLE role_terms (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    value              TEXT NOT NULL,
    kind               TEXT NOT NULL CHECK (kind IN ('canonical', 'exclusion')),
    jurisdiction_ocdid TEXT,                      -- NULL = global; state ocdid = state; place ocdid = local
    display_name       TEXT,                      -- only meaningful for canonical
    is_unique          BOOLEAN NOT NULL DEFAULT FALSE,  -- only meaningful for canonical
    priority           INTEGER NOT NULL DEFAULT 0,      -- only meaningful for canonical
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT role_terms_scope_uq UNIQUE NULLS NOT DISTINCT (value, jurisdiction_ocdid)
);

CREATE TABLE role_aliases (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    term_id     UUID NOT NULL REFERENCES role_terms(id) ON DELETE CASCADE,
    value       TEXT NOT NULL,
    source      TEXT NOT NULL CHECK (source IN ('curated', 'confirmed', 'learned')),
    confidence  REAL,                                 -- only meaningful for source='learned'
    disabled_at TIMESTAMPTZ,                          -- append-only: NULL = active
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX role_aliases_active_uq ON role_aliases (term_id, value) WHERE disabled_at IS NULL;
CREATE INDEX role_aliases_value_idx ON role_aliases (value) WHERE disabled_at IS NULL;

-- Reference table for change_logs.type so adding/removing event types is a
-- one-line diff instead of recreating a CHECK constraint each migration.
CREATE TABLE change_log_types (
    type TEXT PRIMARY KEY
);
-- Role taxonomy events: kind ("canonical" | "exclusion") goes in the payload,
-- not the type. Alias changes fold into edit_role's payload (aliases_added /
-- aliases_removed) so there's one event per term per PUT, not one per alias.
INSERT INTO change_log_types (type) VALUES
    ('merge_review'),
    ('close_review'),
    ('add_person'),
    ('edit_person'),
    ('delete_person'),
    ('edit_jurisdiction'),
    ('add_role'),
    ('edit_role'),
    ('delete_role'),
    ('exclude_role'),
    ('include_role');

ALTER TABLE change_logs DROP CONSTRAINT IF EXISTS change_logs_type_valid;
ALTER TABLE change_logs
    ADD CONSTRAINT change_logs_type_fk
    FOREIGN KEY (type) REFERENCES change_log_types(type);

COMMIT;
