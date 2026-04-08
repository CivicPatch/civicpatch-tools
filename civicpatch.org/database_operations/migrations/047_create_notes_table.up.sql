BEGIN;

CREATE TABLE notes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    jurisdiction_ocdid text NOT NULL REFERENCES jurisdictions(jurisdiction_ocdid) ON UPDATE CASCADE ON DELETE RESTRICT,
    body text NOT NULL,
    user_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_notes_jurisdiction_ocdid ON notes (jurisdiction_ocdid);

COMMIT;
