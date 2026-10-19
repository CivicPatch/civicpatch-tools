-- The charter collectors' own spend settings, apart from the scrape's. state_settings and
-- global_settings bound the people collector only (the scrape's scheduling and budget read
-- people_collector runs alone); a collector runs about once a year per jurisdiction, so its caps
-- are one row per kind, not per state.
--
-- The run cap is never "no cap": a runaway jurisdiction must stop, so it is NOT NULL and seeded
-- low. The monthly cap may be NULL, meaning none, as on the scrape's settings.

BEGIN;

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
