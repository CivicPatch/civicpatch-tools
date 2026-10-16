-- Grounded Gemini calls state no cost, and were kept out of the table for it. NULL means "not
-- stated", never free: sums skip it.

BEGIN;

ALTER TABLE llm_calls ALTER COLUMN cost_usd DROP NOT NULL;

COMMIT;
