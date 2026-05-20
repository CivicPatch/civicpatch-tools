BEGIN;

-- Pre-flight: abort if any role-adjacent row points at a (provider, provider_user_id)
-- with no matching user. Orphans are possible because migration 032 dropped the
-- composite FKs from users_pkey CASCADE; nothing has enforced referential integrity
-- on these three tables since then. Fail loudly here rather than mid-migration on
-- ALTER COLUMN ... SET NOT NULL.
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM user_roles ur
    LEFT JOIN users u
      ON u.provider = ur.provider AND u.provider_user_id = ur.provider_user_id
    WHERE u.id IS NULL
  ) THEN
    RAISE EXCEPTION 'orphan rows in user_roles (no matching user). Clean up before retrying.';
  END IF;
  IF EXISTS (
    SELECT 1 FROM api_keys ak
    LEFT JOIN users u
      ON u.provider = ak.provider AND u.provider_user_id = ak.provider_user_id
    WHERE u.id IS NULL
  ) THEN
    RAISE EXCEPTION 'orphan rows in api_keys (no matching user). Clean up before retrying.';
  END IF;
  IF EXISTS (
    SELECT 1 FROM api_usage_limits aul
    LEFT JOIN users u
      ON u.provider = aul.provider AND u.provider_user_id = aul.provider_user_id
    WHERE u.id IS NULL
  ) THEN
    RAISE EXCEPTION 'orphan rows in api_usage_limits (no matching user). Clean up before retrying.';
  END IF;
END$$;

-- user_roles: composite (provider, provider_user_id) → user_id UUID FK to users(id)
ALTER TABLE user_roles ADD COLUMN user_id UUID;
UPDATE user_roles ur
SET user_id = u.id
FROM users u
WHERE u.provider = ur.provider AND u.provider_user_id = ur.provider_user_id;
ALTER TABLE user_roles ALTER COLUMN user_id SET NOT NULL;
ALTER TABLE user_roles DROP CONSTRAINT user_roles_pkey;
ALTER TABLE user_roles ADD CONSTRAINT user_roles_pkey PRIMARY KEY (user_id, role);
ALTER TABLE user_roles ADD CONSTRAINT user_roles_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE user_roles DROP COLUMN provider;
ALTER TABLE user_roles DROP COLUMN provider_user_id;

-- api_keys: composite (provider, provider_user_id) → user_id UUID FK to users(id)
ALTER TABLE api_keys ADD COLUMN user_id UUID;
UPDATE api_keys ak
SET user_id = u.id
FROM users u
WHERE u.provider = ak.provider AND u.provider_user_id = ak.provider_user_id;
ALTER TABLE api_keys ALTER COLUMN user_id SET NOT NULL;
DROP INDEX IF EXISTS idx_api_keys_provider_user;
ALTER TABLE api_keys ADD CONSTRAINT api_keys_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_api_keys_user_id ON api_keys (user_id);
-- Adjacent: hash index for get_user_by_api_key lookups (was missing pre-086)
CREATE INDEX idx_api_keys_api_key_hash ON api_keys (api_key_hash);
ALTER TABLE api_keys DROP COLUMN provider;
ALTER TABLE api_keys DROP COLUMN provider_user_id;

-- api_usage_limits: composite (provider, provider_user_id) → user_id UUID FK to users(id)
-- No plain idx on user_id: the UNIQUE constraint already creates a unique btree
-- that serves all the same queries.
ALTER TABLE api_usage_limits ADD COLUMN user_id UUID;
UPDATE api_usage_limits aul
SET user_id = u.id
FROM users u
WHERE u.provider = aul.provider AND u.provider_user_id = aul.provider_user_id;
ALTER TABLE api_usage_limits ALTER COLUMN user_id SET NOT NULL;
DROP INDEX IF EXISTS idx_api_usage_limits_provider_user;
ALTER TABLE api_usage_limits DROP CONSTRAINT api_usage_limits_provider_provider_user_id_key;
ALTER TABLE api_usage_limits ADD CONSTRAINT api_usage_limits_user_id_key UNIQUE (user_id);
ALTER TABLE api_usage_limits ADD CONSTRAINT api_usage_limits_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE api_usage_limits DROP COLUMN provider;
ALTER TABLE api_usage_limits DROP COLUMN provider_user_id;

COMMIT;
