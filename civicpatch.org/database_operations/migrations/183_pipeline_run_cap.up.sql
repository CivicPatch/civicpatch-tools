-- The cap a run was dispatched under, resolved once and recorded on the run.
--
-- Resolved at INSERT from `state_settings`, not by the caller: two dispatch paths register runs
-- (a single scrape and a state batch), and a value each of them has to remember to look up is a
-- value one of them will eventually forget. A scalar subquery cannot be bypassed.
--
-- NULL means the state set none, so the run inherits `pipeline.yml`'s default. It also means an
-- unconfigured state and an unknown jurisdiction, which want the same treatment.
--
-- Recorded rather than only resolved because "why did this run stop at $0.05" is a question the
-- llm_calls total alone cannot answer — the cap it was measured against has to be beside it.

BEGIN;

ALTER TABLE pipeline_runs
    ADD COLUMN IF NOT EXISTS pipeline_run_cap_usd numeric(8, 4);

ALTER TABLE pipeline_runs
    DROP CONSTRAINT IF EXISTS pipeline_runs_cap_not_negative;
ALTER TABLE pipeline_runs
    ADD CONSTRAINT pipeline_runs_cap_not_negative
    CHECK (pipeline_run_cap_usd IS NULL OR pipeline_run_cap_usd >= 0);

COMMIT;
