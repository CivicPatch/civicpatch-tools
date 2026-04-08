BEGIN;

-- 1. Drop the UUID Primary Key constraint
-- Postgres usually names this 'users_pkey' once it's promoted
ALTER TABLE users DROP CONSTRAINT IF EXISTS users_pkey;

-- 2. Restore the original Composite Primary Key
-- This assumes your original PK was the combination of these two columns
ALTER TABLE users ADD PRIMARY KEY (provider, provider_user_id);

-- 3. Remove the unique constraint we added to the provider columns 
-- (Since they are now the PK again, a separate UNIQUE constraint is redundant)
ALTER TABLE users DROP CONSTRAINT IF EXISTS unique_provider_user;

-- 4. Drop the UUID column
-- WARNING: This will break any 'submissions' or 'jobs' tables 
-- that were referencing 'users.id'!
ALTER TABLE users DROP COLUMN IF EXISTS id;

COMMIT;