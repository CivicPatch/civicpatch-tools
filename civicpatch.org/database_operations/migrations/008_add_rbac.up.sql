BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
    CREATE TYPE user_role AS ENUM ('member', 'admin');
  END IF;
END$$;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS role user_role NOT NULL DEFAULT 'member';

CREATE INDEX IF NOT EXISTS idx_api_keys_provider_user ON api_keys (provider, provider_user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_revoked ON api_keys (revoked_at);

COMMIT;