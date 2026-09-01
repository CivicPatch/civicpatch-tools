-- Exactly reverses 155. An index carries no data, so the round trip is clean.
BEGIN;

DROP INDEX IF EXISTS idx_change_logs_changeset_id;

COMMIT;
