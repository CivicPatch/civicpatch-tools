BEGIN;

-- All data from these columns was synced to the requests table in migration 035.
-- The columns are no longer referenced in application code.
ALTER TABLE jobs
  DROP COLUMN IF EXISTS job_type_to_delete,
  DROP COLUMN IF EXISTS jurisdiction_ocdid_to_delete,
  DROP COLUMN IF EXISTS arguments_json_to_delete,
  DROP COLUMN IF EXISTS data_json_to_delete,
  DROP COLUMN IF EXISTS review_json_to_delete,
  DROP COLUMN IF EXISTS pull_request_url_to_delete,
  DROP COLUMN IF EXISTS pull_request_status_to_delete,
  DROP COLUMN IF EXISTS pull_request_merged_at_to_delete;

COMMIT;
