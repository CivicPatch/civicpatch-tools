-- Deliberately a no-op. The snapshot's rows are gone and cannot be derived.
--
-- The tempting version of this file recreates the table empty so the schema "matches". Do not:
-- 117's down is `UPDATE requests … FROM publish_timestamp_backup_117`, which against an empty
-- table updates zero rows and reports success. Rolling back 117 would then silently leave the
-- re-stamped values in place while appearing to have restored them.
--
-- Leaving the table absent makes that rollback fail loudly with "relation does not exist",
-- which is the correct outcome: the operator needs to know the restore data is gone and reach
-- for a database backup instead.
BEGIN;

-- Nothing to undo.

COMMIT;
