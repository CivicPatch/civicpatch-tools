-- Which pipeline a run is an attempt of. The run machinery (the spend cap, llm_calls, issues,
-- cancel, the stale sweep) is shared by every pipeline; the scrape's scheduling (the cooldown,
-- candidate selection, the in-flight lane, the per-run averages) filters on its own kind, so a
-- governing-law collection never resets a jurisdiction's scrape cooldown or blocks a scrape.
--
-- Every existing row is a scrape. The default only backfills them and is dropped after, as
-- 153 did for changesets.kind: a writer that does not say which pipeline it is should fail.

BEGIN;

ALTER TABLE pipeline_runs ADD COLUMN IF NOT EXISTS kind text NOT NULL DEFAULT 'people_collector';
ALTER TABLE pipeline_runs ALTER COLUMN kind DROP DEFAULT;

ALTER TABLE pipeline_runs DROP CONSTRAINT IF EXISTS pipeline_runs_kind_check;
ALTER TABLE pipeline_runs ADD CONSTRAINT pipeline_runs_kind_check CHECK (
    kind IN ('people_collector', 'governing_law_collector', 'organizations_collector')
);

COMMIT;
