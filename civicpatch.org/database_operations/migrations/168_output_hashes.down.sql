-- Exactly reverses the up. Dropping the table loses only the gate's memory: every target then
-- looks unwritten, so the next sweep writes each once and refills it.

BEGIN;

DROP TABLE IF EXISTS output_hashes;

COMMIT;
