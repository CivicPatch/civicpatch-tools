BEGIN;

-- Add id column if it doesn't exist
ALTER TABLE people ADD COLUMN IF NOT EXISTS id UUID;

-- Backfill id values for existing rows where id is NULL
UPDATE people SET id = gen_random_uuid() WHERE id IS NULL;

-- Set NOT NULL constraint on id if not already set
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_name='people' AND column_name='id' AND is_nullable='YES'
    ) THEN
        ALTER TABLE people ALTER COLUMN id SET NOT NULL;
    END IF;
END$$;

-- Add primary key on id if it doesn't exist
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