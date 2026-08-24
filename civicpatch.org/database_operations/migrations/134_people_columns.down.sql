BEGIN;

-- `data` was never stopped being written, so dropping these loses nothing.
ALTER TABLE people
    DROP COLUMN name,
    DROP COLUMN other_names,
    DROP COLUMN phones,
    DROP COLUMN emails,
    DROP COLUMN urls,
    DROP COLUMN source_urls,
    DROP COLUMN image,
    DROP COLUMN cdn_image,
    DROP COLUMN start_date,
    DROP COLUMN end_date;

COMMIT;
