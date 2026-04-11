BEGIN;
ALTER TABLE requests RENAME COLUMN data_json TO result_data;
COMMIT;
