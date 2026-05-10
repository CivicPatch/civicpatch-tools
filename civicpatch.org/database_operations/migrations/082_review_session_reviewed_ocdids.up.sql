BEGIN;

-- Array of jurisdictions this session has already reviewed.
-- Eliminates the need to JOIN entries on every card allocation.
ALTER TABLE review_sessions ADD COLUMN reviewed_ocdids TEXT[] NOT NULL DEFAULT '{}';

-- Enforce at the DB level: one active claim per jurisdiction at a time.
-- Sessions purge claimed entries on end, so this constraint is naturally released.
-- The existing UniqueViolation retry in the router handles the rare concurrent collision.
CREATE UNIQUE INDEX idx_review_session_entries_active_claim
    ON review_session_entries (jurisdiction_ocdid)
    WHERE status = 'claimed';

COMMIT;
