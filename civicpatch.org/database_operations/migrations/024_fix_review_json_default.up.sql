BEGIN;

ALTER TABLE jobs ALTER COLUMN review_json SET DEFAULT '{}';
UPDATE jobs SET review_json = '{}' WHERE review_json = '[]';

COMMIT;
