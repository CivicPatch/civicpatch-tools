BEGIN;

UPDATE jobs SET review_json = '[]' WHERE review_json = '{}';
ALTER TABLE jobs ALTER COLUMN review_json SET DEFAULT '[]';

COMMIT;
