BEGIN;
ALTER TABLE jobs RENAME COLUMN result_json TO data_json;
COMMIT;
