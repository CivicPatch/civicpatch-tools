BEGIN;

-- Reverses exactly what the up wrote, keyed on the fingerprint it left: `dismissed_at` equal
-- to the run's own timestamp with no resolving user. A request dismissed any other way has a
-- different timestamp or a user, so it is left alone.
UPDATE requests r
   SET dismissed_at = NULL
  FROM pipeline_runs pr
 WHERE pr.request_id = r.id
   AND pr.status IN ('CANCELLED', 'ERROR')
   AND r.published_at IS NULL
   AND r.resolved_by_user_id IS NULL
   AND r.dismissed_at = COALESCE(pr.updated_at, pr.created_at);

COMMIT;
