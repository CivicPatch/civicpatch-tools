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
    pipeline_run_cap_usd     numeric(8, 4),    -- NULL = inherit pipeline.yml's pipeline_run_cap_usd
    monthly_cap_usd    numeric(8, 4),    -- NULL = no monthly cap for this state
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
        (pipeline_run_cap_usd IS NULL OR pipeline_run_cap_usd >= 0)
        AND (monthly_cap_usd IS NULL OR monthly_cap_usd >= 0)
    );

-- The monthly cap for everything, across every state. The per-state caps do not add up to a promise: fifty states
-- at $2 is $100 even when the month's intent was $40, and every state added raises the implied
-- cap silently.
--
-- A single-row table, and the CHECK says so rather than a comment hoping it stays that way. A
-- table and not an env var because an admin sets it at runtime — a redeploy is not a budget
-- control.
--
-- `monthly_cap_usd` on purpose, the same name the per-state table uses: one concept at two
-- scopes, told apart by which table it is in. "Global" rather than "fleet" because
-- `can_write_global_config` is already this codebase's word for config at this scope, and
-- "fleet" has never appeared in front of a user.
--
-- It is a shared cap, not an allocation: states draw from it first-come, and the per-state
-- monthly cap is what stops one state emptying it. SUM(state_settings.monthly_cap_usd) may
-- therefore exceed this, and the UI shows that rather than refusing it.
CREATE TABLE IF NOT EXISTS global_settings (
    id                 integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    monthly_cap_usd   numeric(10, 4),   -- NULL = no global cap
    updated_by_user_id uuid REFERENCES users(id),
    updated_at         timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE global_settings
    DROP CONSTRAINT IF EXISTS global_settings_cap_not_negative;
ALTER TABLE global_settings
    ADD CONSTRAINT global_settings_cap_not_negative
    CHECK (monthly_cap_usd IS NULL OR monthly_cap_usd >= 0);

-- The row exists from the start, so every reader is a plain SELECT rather than one that has to
-- cope with no row. A NULL cap means no global cap, which is the safe default.
INSERT INTO global_settings (id, monthly_cap_usd)
VALUES (1, NULL)
ON CONFLICT (id) DO NOTHING;

COMMIT;
