BEGIN;

CREATE INDEX IF NOT EXISTS idx_people_jurisdiction_ocdid ON people (jurisdiction_ocdid);

COMMIT;
