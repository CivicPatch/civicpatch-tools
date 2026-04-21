BEGIN;

-- For each jurisdiction, supersede any pending error-category pipeline issues
-- that do not belong to that jurisdiction's most recent pipeline run.
--
-- "Most recent run" = the request with the latest created_at for each jurisdiction_ocdid.
-- Issues are linked to jurisdictions via the requests table through request_ids.
WITH latest_run_per_jurisdiction AS (
    SELECT DISTINCT ON (jurisdiction_ocdid)
        id::text AS request_id,
        jurisdiction_ocdid
    FROM requests
    WHERE jurisdiction_ocdid IS NOT NULL
    ORDER BY jurisdiction_ocdid, created_at DESC
),
issues_to_supersede AS (
    SELECT DISTINCT pi.id
    FROM pipeline_issues pi
    JOIN requests r ON r.id::text = ANY(pi.request_ids)
    JOIN latest_run_per_jurisdiction lr ON lr.jurisdiction_ocdid = r.jurisdiction_ocdid
    WHERE pi.category = 'error'
      AND pi.status = 'pending'
      AND NOT (lr.request_id = ANY(pi.request_ids))
)
UPDATE pipeline_issues
SET status = 'superseded', resolved_at = NOW()
WHERE id IN (SELECT id FROM issues_to_supersede);

COMMIT;
