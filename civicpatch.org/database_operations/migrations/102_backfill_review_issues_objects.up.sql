BEGIN;

-- Structured reviewer issues (slice 2) changed review_json.issues from a list of plain
-- strings to a list of {code, message, person_ids, field} objects. New pipeline runs write
-- objects; rows written before this deploy still hold strings. Collapse the two shapes here
-- so every consumer (CSV export, review checklist/table) can assume objects and drop the
-- dual-model string-vs-object branching at read time.
--
-- Legacy strings carry no code/person_ids/field (those never existed), and some map to codes
-- removed in slice 2, so a code cannot be faithfully reconstructed. We keep only the message:
-- string s -> {"message": s}. Per-row anchoring (person_ids) stays absent on these, which
-- correctly degrades to list-level display.
--
-- Idempotent: only rows containing at least one string element are touched; already-object
-- arrays are left as-is. WITH ORDINALITY + ORDER BY preserves issue order.

UPDATE requests
SET review_json = jsonb_set(
    review_json,
    '{issues}',
    (
        SELECT jsonb_agg(
            CASE
                WHEN jsonb_typeof(elem) = 'string'
                THEN jsonb_build_object('message', elem #>> '{}')
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
      WHERE jsonb_typeof(e) = 'string'
  );

COMMIT;
