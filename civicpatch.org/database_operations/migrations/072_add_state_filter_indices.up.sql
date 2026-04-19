BEGIN;

CREATE INDEX IF NOT EXISTS idx_requests_jurisdiction_ocdid ON requests (jurisdiction_ocdid);
CREATE INDEX IF NOT EXISTS idx_pull_requests_status ON pull_requests (status);

COMMIT;
