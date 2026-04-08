BEGIN;

DROP TABLE IF EXISTS api_usage_limits;

DROP INDEX IF EXISTS idx_api_usage_limits_provider_user;

COMMIT;