BEGIN;

-- Remove the notes feature (#2392). The jurisdiction-curation history it held is
-- superseded by change_logs; the dismiss flow no longer records a note.
DROP TABLE notes;

COMMIT;
