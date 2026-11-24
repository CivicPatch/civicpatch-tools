-- Every pipeline's cadence and caps, per state: the scrape's from state_settings, pipelines 1 and 2's
-- run caps copied to each state from collector_settings. Their monthly caps become per state and start
-- empty: the global cap now bounds every pipeline. The old tables go in a later migration.

BEGIN;

CREATE TABLE IF NOT EXISTS pipeline_settings (
    state                text NOT NULL,
    kind                 text NOT NULL,
    cadence_days         integer,
    cadence_anchor       date,
    pipeline_run_cap_usd numeric(8,4),
    monthly_cap_usd      numeric(8,4),
    updated_by_user_id   uuid REFERENCES users(id),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (state, kind)
);

ALTER TABLE pipeline_settings DROP CONSTRAINT IF EXISTS pipeline_settings_kind_check;
ALTER TABLE pipeline_settings ADD CONSTRAINT pipeline_settings_kind_check CHECK (
    kind IN ('people_collector', 'governing_law_collector', 'organizations_collector')
);

ALTER TABLE pipeline_settings DROP CONSTRAINT IF EXISTS pipeline_settings_cadence_days_positive;
ALTER TABLE pipeline_settings ADD CONSTRAINT pipeline_settings_cadence_days_positive CHECK (
    cadence_days IS NULL OR cadence_days > 0
);

ALTER TABLE pipeline_settings DROP CONSTRAINT IF EXISTS pipeline_settings_caps_not_negative;
ALTER TABLE pipeline_settings ADD CONSTRAINT pipeline_settings_caps_not_negative CHECK (
    (pipeline_run_cap_usd IS NULL OR pipeline_run_cap_usd >= 0) AND (monthly_cap_usd IS NULL OR monthly_cap_usd >= 0)
);

INSERT INTO pipeline_settings
    (state, kind, cadence_days, cadence_anchor, pipeline_run_cap_usd, monthly_cap_usd, updated_by_user_id, updated_at)
SELECT state, 'people_collector', cadence_days, cadence_anchor, pipeline_run_cap_usd, monthly_cap_usd,
       updated_by_user_id, updated_at
FROM state_settings
ON CONFLICT (state, kind) DO NOTHING;

INSERT INTO pipeline_settings (state, kind, pipeline_run_cap_usd, updated_by_user_id, updated_at)
SELECT states.state, cs.kind, cs.pipeline_run_cap_usd, cs.updated_by_user_id, cs.updated_at
FROM (SELECT DISTINCT state FROM jurisdictions WHERE state IS NOT NULL) states
CROSS JOIN collector_settings cs
ON CONFLICT (state, kind) DO NOTHING;

COMMIT;
