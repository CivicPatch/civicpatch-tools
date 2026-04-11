BEGIN;
ALTER TABLE requests RENAME COLUMN result_data TO data_json;
COMMIT;
