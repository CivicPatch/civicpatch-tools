BEGIN;

-- `people.data` becomes columns. Expand only: `data` stays and stays authoritative until every
-- reader has moved, so this migration changes nothing on its own.
--
-- Why now: an assertion's `field_path` has to name something stable, and a dotted path into a
-- blob is not that. A correction overlay was written and deleted on 2026-08-21 for exactly this
-- reason — it leaned on `office.name`. With columns, `field_path` is a column name and the
-- publish merge becomes a dict update.
--
-- Measured on dev across all 20,712 rows before writing this: 14 keys, present on every row,
-- every array actually an array, `name` never null or empty. The COALESCE below is for prod,
-- which is not byte-identical to dev — a migration must not fail halfway on one odd row.
--
-- `office` is deliberately NOT a column. Role and division live on posts/memberships (118), and
-- 20,687 of 20,712 people already have a membership carrying them. Storing it again would be a
-- third copy of an answer two tables already give.
--
-- `id`, `jurisdiction_ocdid` and `updated_at` are not added either: `data` duplicates columns
-- that already exist, and that duplication is part of what this removes.
ALTER TABLE people
    ADD COLUMN name        text,
    ADD COLUMN other_names text[] NOT NULL DEFAULT '{}',
    ADD COLUMN phones      text[] NOT NULL DEFAULT '{}',
    ADD COLUMN emails      text[] NOT NULL DEFAULT '{}',
    ADD COLUMN urls        text[] NOT NULL DEFAULT '{}',
    ADD COLUMN source_urls text[] NOT NULL DEFAULT '{}',
    ADD COLUMN image       text,
    ADD COLUMN cdn_image   text,
    -- Text, not date: sources give partial dates ("2024", "2024-01") and Popolo allows them.
    -- Casting here would either fail or invent a precision the source never had.
    ADD COLUMN start_date  text,
    ADD COLUMN end_date    text;

UPDATE people SET
    name        = data->>'name',
    other_names = ARRAY(SELECT jsonb_array_elements_text(COALESCE(data->'other_names', '[]'::jsonb))),
    phones      = ARRAY(SELECT jsonb_array_elements_text(COALESCE(data->'phones',      '[]'::jsonb))),
    emails      = ARRAY(SELECT jsonb_array_elements_text(COALESCE(data->'emails',      '[]'::jsonb))),
    urls        = ARRAY(SELECT jsonb_array_elements_text(COALESCE(data->'urls',        '[]'::jsonb))),
    source_urls = ARRAY(SELECT jsonb_array_elements_text(COALESCE(data->'source_urls', '[]'::jsonb))),
    image       = data->>'image',
    cdn_image   = data->>'cdn_image',
    start_date  = data->>'start_date',
    end_date    = data->>'end_date';

-- `name` is NOT NULL in the data but the constraint is deliberately NOT set here. Every
-- existing writer inserts `data` alone, so requiring it now would reject them — which is the
-- opposite of expand-only. It goes in with the contract migration, once writers populate the
-- columns and `data` is on its way out.

COMMENT ON COLUMN people.name IS
    'Nullable only during the transition: writers still populate people.data. NOT NULL comes with the contract migration.';

COMMIT;
