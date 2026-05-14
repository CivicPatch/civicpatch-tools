BEGIN;

ALTER TABLE jurisdictions
    ADD COLUMN level TEXT NOT NULL DEFAULT 'local';

CREATE INDEX idx_jurisdictions_level ON jurisdictions (level);

COMMIT;
