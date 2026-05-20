BEGIN;

-- api_usage_limits: reverse
ALTER TABLE api_usage_limits ADD COLUMN provider TEXT;
ALTER TABLE api_usage_limits ADD COLUMN provider_user_id TEXT;
UPDATE api_usage_limits aul
SET provider = u.provider, provider_user_id = u.provider_user_id
FROM users u
WHERE u.id = aul.user_id;
ALTER TABLE api_usage_limits ALTER COLUMN provider SET NOT NULL;
ALTER TABLE api_usage_limits ALTER COLUMN provider_user_id SET NOT NULL;
ALTER TABLE api_usage_limits DROP CONSTRAINT api_usage_limits_user_id_fkey;
ALTER TABLE api_usage_limits DROP CONSTRAINT api_usage_limits_user_id_key;
ALTER TABLE api_usage_limits ADD CONSTRAINT api_usage_limits_provider_provider_user_id_key UNIQUE (provider, provider_user_id);
CREATE INDEX idx_api_usage_limits_provider_user ON api_usage_limits (provider, provider_user_id);
ALTER TABLE api_usage_limits DROP COLUMN user_id;

-- api_keys: reverse
ALTER TABLE api_keys ADD COLUMN provider TEXT DEFAULT 'github';
ALTER TABLE api_keys ADD COLUMN provider_user_id TEXT;
UPDATE api_keys ak
SET provider = u.provider, provider_user_id = u.provider_user_id
FROM users u
WHERE u.id = ak.user_id;
ALTER TABLE api_keys ALTER COLUMN provider SET NOT NULL;
ALTER TABLE api_keys ALTER COLUMN provider_user_id SET NOT NULL;
DROP INDEX IF EXISTS idx_api_keys_user_id;
DROP INDEX IF EXISTS idx_api_keys_api_key_hash;
ALTER TABLE api_keys DROP CONSTRAINT api_keys_user_id_fkey;
CREATE INDEX idx_api_keys_provider_user ON api_keys (provider, provider_user_id);
ALTER TABLE api_keys DROP COLUMN user_id;

-- user_roles: reverse
ALTER TABLE user_roles ADD COLUMN provider VARCHAR(50);
ALTER TABLE user_roles ADD COLUMN provider_user_id VARCHAR(255);
UPDATE user_roles ur
SET provider = u.provider, provider_user_id = u.provider_user_id
FROM users u
WHERE u.id = ur.user_id;
ALTER TABLE user_roles ALTER COLUMN provider SET NOT NULL;
ALTER TABLE user_roles ALTER COLUMN provider_user_id SET NOT NULL;
ALTER TABLE user_roles DROP CONSTRAINT user_roles_user_id_fkey;
ALTER TABLE user_roles DROP CONSTRAINT user_roles_pkey;
ALTER TABLE user_roles ADD CONSTRAINT user_roles_pkey PRIMARY KEY (provider, provider_user_id, role);
ALTER TABLE user_roles DROP COLUMN user_id;

COMMIT;
