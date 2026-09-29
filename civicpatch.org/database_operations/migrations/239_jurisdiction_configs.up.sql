-- open-data's config files (roles and government forms, by layer), stored whole as each merge
-- syncs them. A role records the file that defines it; every existing role but `unmatched`
-- (owned by migration 118) starts in the country file, which the next sync makes true.

BEGIN;

CREATE TABLE IF NOT EXISTS jurisdiction_configs (
    path        text PRIMARY KEY CHECK (path <> ''),
    content     jsonb NOT NULL,
    commit_sha  text NOT NULL,
    synced_at   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE roles ADD COLUMN IF NOT EXISTS config_path text;

UPDATE roles
SET config_path = 'data_source/config.yml'
WHERE config_path IS NULL AND id <> 'unmatched';

-- One config file synced after its PR merged: which file, which commit, which forms moved.
INSERT INTO activity_types (type) VALUES ('sync_jurisdiction_config')
    ON CONFLICT (type) DO NOTHING;

COMMIT;
