-- The calls with no stated cost go: NOT NULL cannot hold them.

BEGIN;

DELETE FROM llm_calls WHERE cost_usd IS NULL;
ALTER TABLE llm_calls ALTER COLUMN cost_usd SET NOT NULL;

COMMIT;
