BEGIN;
ALTER TABLE jobs RENAME COLUMN data_json TO result_json;
COMMIT;
