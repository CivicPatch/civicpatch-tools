BEGIN;

CREATE TABLE IF NOT EXISTS api_usage_limits (
    id SERIAL PRIMARY KEY,
    provider TEXT NOT NULL,
    provider_user_id TEXT NOT NULL,
    daily_limit INTEGER NOT NULL,
    UNIQUE(provider, provider_user_id)
);

CREATE INDEX IF NOT EXISTS idx_api_usage_limits_provider_user
    ON api_usage_limits (provider, provider_user_id); 

COMMIT;