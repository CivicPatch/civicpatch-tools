BEGIN;

DROP INDEX IF EXISTS governing_law_source_pages_jurisdiction_ocdid_idx;
DROP TABLE IF EXISTS governing_law_source_pages;

ALTER TABLE jurisdictions DROP COLUMN IF EXISTS extras_governing_law;

COMMIT;
