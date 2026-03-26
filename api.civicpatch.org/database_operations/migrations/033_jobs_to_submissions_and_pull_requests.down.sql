BEGIN;

-- 1. Use CASCADE to break all foreign key tethers immediately
-- This handles the "DependentObjectsStillExist" error by force
DROP TABLE IF EXISTS pull_requests CASCADE;
DROP TABLE IF EXISTS requests CASCADE;
DROP TABLE IF EXISTS submissions CASCADE;

-- 2. Restore the Jobs table to its original state
DO $$ 
BEGIN 
    -- Check if we need to rename the column back
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name='jobs' AND column_name='run_url') THEN
        ALTER TABLE jobs RENAME COLUMN run_url TO job_run_url;
    END IF;
END $$;

-- 3. Remove the link columns from Jobs
ALTER TABLE jobs DROP COLUMN IF EXISTS request_id;
ALTER TABLE jobs DROP COLUMN IF EXISTS submission_id;

COMMIT;