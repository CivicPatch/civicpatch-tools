-- review_json issue codes: missing_official -> absent_official, extra_official -> new_official.
--
-- The codes are named for what was observed rather than what it means. "Missing" and "extra"
-- describe a set difference; the reviewer's actual question is whether an absence is a
-- departure and whether a new name is an arrival, and the code should not answer that for
-- them. `absent_official` and `new_official` state the evidence and leave the conclusion.
--
-- Safe to rewrite in place, unlike the change_log_types values: `review_json` is a jsonb blob
-- with no referential integrity, so nothing points at these strings. The frontend reads them
-- to place markers, so old rows must be rewritten or historical cards lose their annotations.
--
-- Scoped to the `issues` array, not a whole-document text replace: a person genuinely named
-- "extra_official" in some field would otherwise be rewritten too.
--
-- Idempotent: rows already carrying the new codes match nothing.
BEGIN;

UPDATE requests
   SET review_json = jsonb_set(
           review_json,
           '{issues}',
           (
               SELECT jsonb_agg(
                   CASE issue->>'code'
                       WHEN 'missing_official' THEN jsonb_set(issue, '{code}', '"absent_official"')
                       WHEN 'extra_official'   THEN jsonb_set(issue, '{code}', '"new_official"')
                       ELSE issue
                   END
                   ORDER BY ordinality
               )
               FROM jsonb_array_elements(review_json->'issues') WITH ORDINALITY AS t(issue, ordinality)
           )
       )
 WHERE jsonb_typeof(review_json->'issues') = 'array'
   AND EXISTS (
       SELECT 1 FROM jsonb_array_elements(review_json->'issues') AS issue
       WHERE issue->>'code' IN ('missing_official', 'extra_official')
   );

COMMIT;
