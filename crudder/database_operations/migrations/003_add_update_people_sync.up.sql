BEGIN;

CREATE TABLE IF NOT EXISTS sync_log (
    sync_id SERIAL PRIMARY KEY,
    sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    files_updated INTEGER,
    git_commit TEXT
);

-- This block finds the existing PK constraint name and drops it.
-- This handles system-generated names which can differ between environments.
DO $$
DECLARE
    pk_name TEXT;
BEGIN
    -- Query the system catalog to find the name of the Primary Key ('p') on the 'people' table.
    SELECT c.conname
    INTO pk_name
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    WHERE t.relname = 'people' AND c.contype = 'p';

    -- Check if a name was found and drop the constraint if it exists.
    IF pk_name IS NOT NULL THEN
        EXECUTE 'ALTER TABLE people DROP CONSTRAINT ' || quote_ident(pk_name) || ';';
        RAISE NOTICE 'Dropped old primary key constraint: %', pk_name;
    ELSE
        RAISE NOTICE 'No primary key constraint found to drop on table people.';
    END IF;
END $$;

TRUNCATE TABLE people;

ALTER TABLE people
    ADD CONSTRAINT pk_people_ocdid PRIMARY KEY (jurisdiction_ocdid),

    ADD COLUMN file_path TEXT,
    ADD COLUMN git_commit TEXT,
    ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    DROP COLUMN name;

COMMIT;
