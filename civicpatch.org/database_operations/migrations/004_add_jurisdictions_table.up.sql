BEGIN;

CREATE TABLE IF NOT EXISTS jurisdictions (
    jurisdiction_ocdid TEXT PRIMARY KEY,
    state TEXT,
    file_path TEXT,
    git_commit TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMIT;
