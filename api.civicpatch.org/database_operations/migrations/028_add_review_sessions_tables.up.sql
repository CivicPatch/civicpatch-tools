BEGIN;

CREATE TABLE IF NOT EXISTS review_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    provider_user_id TEXT NOT NULL,
    session_date DATE NOT NULL DEFAULT CURRENT_DATE,
    state_code TEXT NOT NULL,
    daily_goal INTEGER NOT NULL DEFAULT 10,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (provider, provider_user_id, session_date, state_code)
);

CREATE TABLE IF NOT EXISTS review_session_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    review_session_id UUID NOT NULL REFERENCES review_sessions(id),
    request_id VARCHAR(255) NOT NULL,
    jurisdiction_ocdid TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'viewing', -- 'viewing' | 'skipped'
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_review_session_entries_review_session_id
    ON review_session_entries (review_session_id);

-- Enforces at most one active viewer per jurisdiction at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_review_session_entries_one_viewer
    ON review_session_entries (jurisdiction_ocdid)
    WHERE status = 'viewing';

COMMIT;
