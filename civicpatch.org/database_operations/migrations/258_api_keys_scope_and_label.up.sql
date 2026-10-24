-- What a key may reach (ApiKeyScope): `agent` only /mcp and the roster comparisons, `full` all
-- its owner may. Added as `full` so existing keys keep working, then new keys default to `agent`.
-- `last_used_at` is written at most once a minute per key (`touch_api_key`).

BEGIN;

ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS scope text NOT NULL DEFAULT 'full';
ALTER TABLE api_keys ALTER COLUMN scope SET DEFAULT 'agent';

ALTER TABLE api_keys DROP CONSTRAINT IF EXISTS api_keys_scope_check;
ALTER TABLE api_keys ADD CONSTRAINT api_keys_scope_check CHECK (scope IN ('full', 'agent'));

ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS label text;
ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS last_used_at timestamptz;

COMMIT;
