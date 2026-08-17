-- Exact reverse of 112. Indexes and constraints go with the table.
-- Idempotent: DROP ... IF EXISTS is a no-op when 112 was never applied.
BEGIN;

DROP TABLE IF EXISTS source_records;

COMMIT;
