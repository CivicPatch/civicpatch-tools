BEGIN;

-- drop indexes added in the up migration
DROP INDEX IF EXISTS idx_api_keys_provider_user;
DROP INDEX IF EXISTS idx_api_keys_revoked;

-- remove the role column from users
ALTER TABLE users
  DROP COLUMN IF EXISTS role;

-- drop the enum type if it exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
    DROP TYPE user_role;
  END IF;
END$$;

COMMIT;