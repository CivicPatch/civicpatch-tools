BEGIN;

-- Drop status column if it exists
ALTER TABLE people DROP COLUMN IF EXISTS status;

-- Drop id column if it exists
ALTER TABLE people DROP COLUMN IF EXISTS id;

-- Drop primary key constraint if it exists
ALTER TABLE people DROP CONSTRAINT IF EXISTS people_pkey;

-- Optionally, restore the 'data' column if needed:
-- ALTER TABLE people ADD COLUMN IF NOT EXISTS data JSONB;

COMMIT;