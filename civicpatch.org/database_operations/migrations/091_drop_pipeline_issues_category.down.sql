BEGIN;

-- Restores the column shape. Original per-row values can't be recovered after the drop;
-- existing rows backfill to 'issue' (the value the pipeline-emitted path used).
ALTER TABLE pipeline_issues ADD COLUMN category TEXT;
UPDATE pipeline_issues SET category = 'issue' WHERE category IS NULL;
ALTER TABLE pipeline_issues ALTER COLUMN category SET NOT NULL;
ALTER TABLE pipeline_issues ADD CONSTRAINT pipeline_issues_category_check
    CHECK (category = ANY (ARRAY['error'::text, 'issue'::text]));

COMMIT;
