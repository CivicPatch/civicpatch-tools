-- Where a scrape's cadence and its money live. Two tables in one migration because they are one
-- feature: the same enforcement seam reads both, the UI edits both, and there is no state of the
-- world that wants one without the other. Splitting them would only mean rolling the feature
-- back in two steps.
--
-- Every nullable column means *inherit* or *none*, never zero. That is what lets the page say
-- `manual` and `$0.20 default` without a second flag to tell those apart. Zero is legal
-- everywhere it appears and means "spend nothing" — a real setting, and not the same as NULL.

BEGIN;

-- Cadence and budget per state. One row per state, not two tables, because the UI edits both
-- behind one modal and one save: they are one decision.
--
-- No row for a state is identical to a row of all NULLs, so nothing has to seed 50 rows.
CREATE TABLE IF NOT EXISTS state_settings (
    state              text PRIMARY KEY,
    cadence_days       integer,          -- NULL = manual, the page's own word for it
    cadence_start      date,             -- ScheduleIntervalSpec(offset=), staggers the states
    scrape_cap_usd     numeric(8, 4),    -- NULL = inherit pipeline.yml's pipeline_run_cost_limit
    monthly_cap_usd    numeric(8, 4),    -- NULL = no monthly ceiling for this state
    updated_by_user_id uuid REFERENCES users(id),
    updated_at         timestamptz NOT NULL DEFAULT now()
);

-- A cadence of zero days schedules an infinite loop and a negative one is meaningless. Money
-- cannot be negative; zero can, and means spend nothing.
ALTER TABLE state_settings
    DROP CONSTRAINT IF EXISTS state_settings_cadence_days_positive;
ALTER TABLE state_settings
    ADD CONSTRAINT state_settings_cadence_days_positive
    CHECK (cadence_days IS NULL OR cadence_days > 0);

ALTER TABLE state_settings
    DROP CONSTRAINT IF EXISTS state_settings_caps_not_negative;
ALTER TABLE state_settings
    ADD CONSTRAINT state_settings_caps_not_negative
    CHECK (
        (scrape_cap_usd IS NULL OR scrape_cap_usd >= 0)
        AND (monthly_cap_usd IS NULL OR monthly_cap_usd >= 0)
    );

-- The fleet's own monthly ceiling. The per-state caps do not add up to a promise: fifty states
-- at $2 is $100 even when the month's intent was $40, and every state added raises the implied
-- ceiling silently.
--
-- A single-row table, and the CHECK says so rather than a comment hoping it stays that way. A
-- table and not an env var because an admin sets it at runtime — a redeploy is not a budget
-- control.
--
-- The pool is a shared ceiling, not an allocation: states draw from it first-come, and the
-- per-state monthly cap is what stops one state emptying it. SUM(monthly_cap_usd) across states
-- may therefore exceed the pool, and the UI shows that rather than refusing it.
CREATE TABLE IF NOT EXISTS fleet_settings (
    id                 integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    monthly_pool_usd   numeric(10, 4),   -- NULL = no fleet ceiling
    updated_by_user_id uuid REFERENCES users(id),
    updated_at         timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE fleet_settings
    DROP CONSTRAINT IF EXISTS fleet_settings_pool_not_negative;
ALTER TABLE fleet_settings
    ADD CONSTRAINT fleet_settings_pool_not_negative
    CHECK (monthly_pool_usd IS NULL OR monthly_pool_usd >= 0);

-- The row exists from the start, so every reader is a plain SELECT rather than one that has to
-- cope with no row. A NULL pool means no fleet ceiling, which is the safe default.
INSERT INTO fleet_settings (id, monthly_pool_usd)
VALUES (1, NULL)
ON CONFLICT (id) DO NOTHING;

COMMIT;
