BEGIN;

ALTER TABLE review_session_entries ALTER COLUMN status SET DEFAULT 'deferred';

CREATE UNIQUE INDEX IF NOT EXISTS idx_review_session_entries_one_viewer
    ON review_session_entries (jurisdiction_ocdid)
    WHERE status = 'viewing';

COMMIT;
