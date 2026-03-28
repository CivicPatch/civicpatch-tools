BEGIN;

-- 1. Migrate data to requests
WITH inserted_requests AS (
    INSERT INTO requests (
        status, request_type, jurisdiction_ocdid, 
        arguments_json, result_data, review_json, 
        created_at, updated_at
    )
    SELECT 
        status, job_type, jurisdiction_ocdid, 
        arguments_json, data_json, review_json, 
        created_at, updated_at
    FROM jobs
    RETURNING id, created_at
)
-- 2. Link Jobs to Requests
UPDATE jobs j
SET request_id = ir.id
FROM inserted_requests ir
WHERE j.created_at = ir.created_at;

-- 3. Back-link Requests to Jobs
UPDATE requests r
SET job_id = j.id
FROM jobs j
WHERE r.id = j.request_id::uuid;

-- 4. Port Pull Requests
INSERT INTO pull_requests (request_id, url, status, merged_at, pr_number, created_at, updated_at)
SELECT 
    j.request_id::uuid, j.pull_request_url, j.pull_request_status, j.pull_request_merged_at,
    COALESCE(substring(j.pull_request_url from 'pull/([0-9]+)')::int, 0),
    j.created_at, j.updated_at
FROM jobs j
WHERE j.pull_request_url IS NOT NULL;

-- 5. Back-link Requests to Pull Requests
UPDATE requests r
SET pr_id = p.id
FROM pull_requests p
WHERE r.id = p.request_id::uuid;

-- 6. Simple Renames (No DO block, less risk of syntax error)
-- If these fail because you already renamed them, just comment them out.
ALTER TABLE jobs RENAME COLUMN job_type TO job_type_to_delete;
ALTER TABLE jobs RENAME COLUMN jurisdiction_ocdid TO jurisdiction_ocdid_to_delete;
ALTER TABLE jobs RENAME COLUMN arguments_json TO arguments_json_to_delete;
ALTER TABLE jobs RENAME COLUMN data_json TO data_json_to_delete;
ALTER TABLE jobs RENAME COLUMN review_json TO review_json_to_delete;
ALTER TABLE jobs RENAME COLUMN pull_request_url TO pull_request_url_to_delete;
ALTER TABLE jobs RENAME COLUMN pull_request_status TO pull_request_status_to_delete;
ALTER TABLE jobs RENAME COLUMN pull_request_merged_at TO pull_request_merged_at_to_delete;
COMMIT;