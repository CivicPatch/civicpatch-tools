BEGIN;

-- A sheet import nobody published or dismissed within a week is dismissed by the reaper.
ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_dismissed_reason_valid;
ALTER TABLE changesets ADD CONSTRAINT changesets_dismissed_reason_valid
    CHECK (dismissed_reason IS NULL
           OR dismissed_reason IN ('rejected', 'cancelled', 'errored', 'superseded', 'expired'));

COMMENT ON COLUMN changesets.dismissed_reason IS
    'Why the changeset was dismissed. A person: rejected. A sweep: superseded. The run: errored, cancelled. The import reaper: expired. NULL = published, in flight, or pre-dating this column.';

COMMIT;
