BEGIN;

CREATE TABLE IF NOT EXISTS change_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type TEXT NOT NULL,
    jurisdiction_ocdid TEXT, -- NULL for changes not scoped to a jurisdiction
    request_id TEXT, -- the request the change belongs to; NULL for non-review changes
    changes JSONB, -- type-specific payload; for edit_person a [{field, from, to}] diff
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT change_logs_type_valid CHECK (type IN (
        'merge_review', 'close_review',
        'add_person', 'edit_person', 'delete_person',
        'edit_jurisdiction'
    ))
);

CREATE INDEX IF NOT EXISTS idx_change_logs_jurisdiction_ocdid
    ON change_logs (jurisdiction_ocdid);

CREATE INDEX IF NOT EXISTS idx_change_logs_created_at
    ON change_logs (created_at DESC);

COMMIT;
