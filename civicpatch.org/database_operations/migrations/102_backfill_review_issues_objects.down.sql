BEGIN;

-- Reverse 102: collapse the {message}-only objects this migration created back to their
-- plain message string. Objects that carry a `code` key are full structured issues written
-- by the new pipeline, not artifacts of the up migration, so leave those untouched.

UPDATE requests
SET review_json = jsonb_set(
    review_json,
    '{issues}',
    (
        SELECT jsonb_agg(
            CASE
                WHEN jsonb_typeof(elem) = 'object' AND NOT (elem ? 'code')
                THEN to_jsonb(elem->>'message')
                ELSE elem
            END
            ORDER BY ord
        )
        FROM jsonb_array_elements(review_json->'issues') WITH ORDINALITY AS t(elem, ord)
    )
)
WHERE jsonb_typeof(review_json->'issues') = 'array'
  AND EXISTS (
      SELECT 1
      FROM jsonb_array_elements(review_json->'issues') e
      WHERE jsonb_typeof(e) = 'object' AND NOT (e ? 'code')
  );

COMMIT;
