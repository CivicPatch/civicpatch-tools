BEGIN;

-- Drop primary key constraint on id if it exists
DO $$
DECLARE
    pk_name text;
BEGIN
    SELECT constraint_name INTO pk_name
    FROM information_schema.table_constraints
    WHERE table_name = 'people'
      AND constraint_type = 'PRIMARY KEY';
    IF pk_name IS NOT NULL THEN
        EXECUTE format('ALTER TABLE people DROP CONSTRAINT %I', pk_name);
    END IF;
END$$;

-- Drop id column if it exists
ALTER TABLE people DROP COLUMN IF EXISTS id;

COMMIT;