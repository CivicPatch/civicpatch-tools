BEGIN;

-- The review summary is computed at read now, from the published roster and the one this
-- scrape proposes — both of which the card already fetches.
--
-- It could not be before: `absent_official` compared against the pipeline's own research step,
-- which lived in the workflow context and was stored nowhere, so the summary had to be frozen
-- at ingest and a new heuristic could never reach an old card. The baseline is `people` now.
--
-- The queue's ordering keeps only the post-issue term until the roster checks land in a table
-- (see `.scratch/2026-08-25-retire-review-json.md`, phase 2).
ALTER TABLE requests DROP COLUMN IF EXISTS review_json;

COMMIT;
