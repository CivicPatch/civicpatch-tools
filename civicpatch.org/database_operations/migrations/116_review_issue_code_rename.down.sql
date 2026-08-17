-- Exact reverse of 116. See the up migration for why the codes were renamed.
-- Same in-place jsonb rewrite, scoped to the issues array.
BEGIN;

UPDATE requests
   SET review_json = jsonb_set(
           review_json,
           '{issues}',
           (
               SELECT jsonb_agg(
                   CASE issue->>'code'
                       WHEN 'absent_official' THEN jsonb_set(issue, '{code}', '"missing_official"')
                       WHEN 'new_official'     THEN jsonb_set(issue, '{code}', '"extra_official"')
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
       WHERE issue->>'code' IN ('absent_official', 'new_official')
   );

COMMIT;
