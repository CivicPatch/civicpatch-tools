BEGIN;

-- Requests whose run ended without producing a roster, left at "pending" because nothing
-- translated a terminal run into a terminal request. They are not reviewable — there is no
-- roster to review — but they populated the jurisdiction page's scrape list and, through
-- `peopleEditBlockers`, disabled roster editing for their jurisdiction indefinitely.
--
-- The code path that creates them is fixed (`finalize_pipeline_run`); this settles the ones
-- already on disk.
--
-- Dated from the run, not from now: the scrape died when it died, and stamping migration time
-- would claim a decision was made today. Same reason `_seen_at` refuses write time.
--
-- `resolved_by_user_id` stays NULL — nobody decided this, a machine gave up.
-- `published_at IS NULL` guard: a published request is never retracted by a late failure.
UPDATE requests r
   SET dismissed_at = COALESCE(pr.updated_at, pr.created_at, now())
  FROM pipeline_runs pr
 WHERE pr.request_id = r.id
   AND pr.status IN ('CANCELLED', 'ERROR')
   AND r.published_at IS NULL
   AND r.dismissed_at IS NULL;

COMMIT;
