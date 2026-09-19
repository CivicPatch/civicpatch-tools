BEGIN;

-- Other names a source states outright for this person, as a sheet row's `other_names` does.
-- Empty for a scrape: its aliases are the spellings that differ between its sightings.
ALTER TABLE source_records ADD COLUMN IF NOT EXISTS other_names text[] NOT NULL DEFAULT '{}';

COMMIT;
