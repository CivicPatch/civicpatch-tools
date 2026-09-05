-- Deliberately a no-op. The up deletes rows for a type nothing has produced since 2026-08-16,
-- and deleted rows cannot be reconstructed — there is no source to re-derive them from, which
-- is the point: `parse_label` now recovers the same information from the raw label.
--
-- Rolling back leaves the table without them, which is the same state a fresh database reaches.

BEGIN;

SELECT 1;

COMMIT;
