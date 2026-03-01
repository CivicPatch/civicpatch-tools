BEGIN;

-- Drop constraint if it exists
ALTER TABLE people DROP CONSTRAINT IF EXISTS pk_people_ocdid;

-- Add id column if it doesn't exist
ALTER TABLE people ADD COLUMN IF NOT EXISTS id UUID DEFAULT gen_random_uuid();

-- Add status column if it doesn't exist
ALTER TABLE people ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'current';

-- Backfill id values
UPDATE people SET id = gen_random_uuid() WHERE id IS NULL;

-- Set NOT NULL
ALTER TABLE people ALTER COLUMN id SET NOT NULL;

-- Add primary key only if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'people'::regclass AND contype = 'p'
    ) THEN
        ALTER TABLE people ADD PRIMARY KEY (id);
    END IF;
END$$;

COMMIT;