-- One row per call, so a resubmitted artifact cannot double-count spend.
--
-- `record_calls` runs on the submit path, which is an HTTP endpoint: a scraper that retries
-- after a timeout the server actually completed re-sends the same `costs.json`, and a plain
-- INSERT wrote every call again. Nothing downstream could tell the duplicates apart — the rows
-- are byte-identical except for `id` — so the spend was simply wrong.
--
-- `generation_id` is OpenRouter's id for the call, unique per generation and already stored.
-- Partial, because a row that reached us without one has nothing to dedupe on: the grounded
-- Google calls are kept out of this table entirely, but a gateway added later might not state
-- an id, and those rows should still land.

BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS llm_calls_generation_uq
    ON llm_calls (pipeline_run_id, generation_id)
    WHERE generation_id IS NOT NULL;

COMMIT;
