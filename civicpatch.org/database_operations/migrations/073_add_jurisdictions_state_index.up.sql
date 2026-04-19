BEGIN;

CREATE INDEX IF NOT EXISTS idx_jurisdictions_state ON jurisdictions (state);

COMMIT;
