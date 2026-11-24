BEGIN;

CREATE TABLE IF NOT EXISTS state_settings (
    state                text PRIMARY KEY,
    cadence_days         integer,
    cadence_anchor       date,
    pipeline_run_cap_usd numeric(8,4),
    monthly_cap_usd      numeric(8,4),
    updated_by_user_id   uuid REFERENCES users(id),
    updated_at           timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE state_settings DROP CONSTRAINT IF EXISTS state_settings_cadence_days_positive;
ALTER TABLE state_settings ADD CONSTRAINT state_settings_cadence_days_positive CHECK (cadence_days IS NULL OR cadence_days > 0);
ALTER TABLE state_settings DROP CONSTRAINT IF EXISTS state_settings_caps_not_negative;
ALTER TABLE state_settings ADD CONSTRAINT state_settings_caps_not_negative CHECK (
    (pipeline_run_cap_usd IS NULL OR pipeline_run_cap_usd >= 0) AND (monthly_cap_usd IS NULL OR monthly_cap_usd >= 0)
);
INSERT INTO state_settings (state, cadence_days, cadence_anchor, pipeline_run_cap_usd, monthly_cap_usd, updated_by_user_id, updated_at)
SELECT state, cadence_days, cadence_anchor, pipeline_run_cap_usd, monthly_cap_usd, updated_by_user_id, updated_at
FROM pipeline_settings WHERE kind = 'people_collector'
ON CONFLICT (state) DO NOTHING;

CREATE TABLE IF NOT EXISTS collector_settings (
    kind                 text PRIMARY KEY,
    pipeline_run_cap_usd numeric(8,4) NOT NULL DEFAULT 0.50,
    monthly_cap_usd      numeric(8,4),
    updated_by_user_id   uuid REFERENCES users(id),
    updated_at           timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE collector_settings DROP CONSTRAINT IF EXISTS collector_settings_kind_check;
ALTER TABLE collector_settings ADD CONSTRAINT collector_settings_kind_check CHECK (
    kind IN ('governing_law_collector', 'organizations_collector')
);
ALTER TABLE collector_settings DROP CONSTRAINT IF EXISTS collector_settings_caps_not_negative;
ALTER TABLE collector_settings ADD CONSTRAINT collector_settings_caps_not_negative CHECK (
    pipeline_run_cap_usd >= 0 AND (monthly_cap_usd IS NULL OR monthly_cap_usd >= 0)
);
INSERT INTO collector_settings (kind) VALUES ('governing_law_collector'), ('organizations_collector')
ON CONFLICT (kind) DO NOTHING;

COMMIT;
