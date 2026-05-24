BEGIN;

-- `category` (error|issue) no longer carries meaning: informational events now go to logs,
-- so every persisted issue is actionable. Its lone consumer (the scrape gate) now keys on
-- "any pending issue" instead. The issue's kind lives in `issue_type`.
ALTER TABLE pipeline_issues DROP CONSTRAINT IF EXISTS pipeline_issues_category_check;
ALTER TABLE pipeline_issues DROP COLUMN IF EXISTS category;

COMMIT;
