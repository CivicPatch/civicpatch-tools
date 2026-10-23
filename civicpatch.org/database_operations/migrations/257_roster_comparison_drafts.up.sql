-- An upload sent in batches (by agents whose shell cannot reach the API, so they upload through
-- MCP tools): the header first, rows appended, then compared as one run and deleted. Only its
-- owner may add to it or finish it; a draft nobody finishes expires after a day.

BEGIN;

CREATE TABLE IF NOT EXISTS roster_comparison_drafts (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id  uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at     timestamptz NOT NULL DEFAULT now(),
    state          text NOT NULL,
    source_columns jsonb NOT NULL,
    corrections    jsonb NOT NULL,
    rows           jsonb NOT NULL DEFAULT '[]'::jsonb,
    row_count      integer NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS roster_comparison_drafts_created_at_idx
    ON roster_comparison_drafts (created_at);

COMMIT;
