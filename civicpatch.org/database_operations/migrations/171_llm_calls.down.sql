-- The index goes with the table; naming it separately is for readers, not for postgres.

BEGIN;

DROP INDEX IF EXISTS llm_calls_run_idx;
DROP TABLE IF EXISTS llm_calls;

COMMIT;
