BEGIN;

-- Migration 034 linked jobs -> requests using created_at as the join key,
-- which is non-unique. Jobs with identical timestamps were mislinked, causing
-- requests rows to have wrong or null jurisdiction_ocdid / result_data / review_json.
--
-- The *_to_delete columns on jobs still hold the authoritative source data.
-- This migration re-establishes the correct 1-to-1 link and re-syncs the data.

-- Step 1: Re-link requests.job_id using the tightest available match:
--   created_at + jurisdiction_ocdid + arguments_json.
-- Where that still produces duplicates (identical jobs), the MIN(j.id) wins —
-- consistent and deterministic. Rows already correctly linked are left unchanged.
UPDATE requests r
SET job_id = matched.job_id
FROM (
    SELECT DISTINCT ON (r.id)
        r.id    AS request_id,
        j.id    AS job_id
    FROM requests r
    JOIN jobs j
      ON  j.created_at                   = r.created_at
      AND j.jurisdiction_ocdid_to_delete IS NOT DISTINCT FROM r.jurisdiction_ocdid
      AND j.arguments_json_to_delete     IS NOT DISTINCT FROM r.arguments_json
    ORDER BY r.id, j.id  -- deterministic: pick lowest job id on collision
) matched
WHERE r.id = matched.request_id
  AND r.job_id IS DISTINCT FROM matched.job_id;

-- Step 2: Re-sync the back-reference on jobs.
UPDATE jobs j
SET request_id = r.id
FROM requests r
WHERE r.job_id = j.id
  AND j.request_id::uuid IS DISTINCT FROM r.id;

-- Step 3: Re-copy data columns from the authoritative *_to_delete sources
-- now that the job_id links are correct.
UPDATE requests r
SET
    jurisdiction_ocdid = j.jurisdiction_ocdid_to_delete,
    result_data        = j.data_json_to_delete,
    review_json        = j.review_json_to_delete,
    arguments_json     = COALESCE(j.arguments_json_to_delete, '{}'),
    updated_at         = CURRENT_TIMESTAMP
FROM jobs j
WHERE r.job_id = j.id;

COMMIT;
