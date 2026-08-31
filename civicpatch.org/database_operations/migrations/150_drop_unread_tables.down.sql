-- Restores the three tables empty, and `state_configs` reseeded the way 100 seeded it.
--
-- Lossy, and honestly so, in two places. `sync_log` and `logs` come back with no rows — both
-- were empty when 150 ran, so nothing is actually lost today, but a replay against a database
-- where they were not would not recover them.
--
-- The `synced_files` rows cannot come back at all: they were git blob SHAs, and re-deriving
-- them would mean reading every people file out of open-data to record a cursor that nothing
-- reads. The cost of not restoring them is one wasted pass on a direction that no longer runs.
--
-- `state_configs` returns *without* `min_scraped_at` — 103 dropped that column, so restoring
-- it here would undo 103 as well.
--
-- Its **row count will not match** what the up migration dropped: 9 rows became 15 on the
-- first round trip, because 100 seeded from the states that had jurisdictions *then* and this
-- reseeds from the states that have them *now*. That is the honest reversal for a table whose
-- rows are derived rather than authored — it restores what 100 would produce today, and the
-- table carries no attributes, so which states are listed holds no information to lose.
-- Stashing 9 rows of pure key in a backup table to make the count match would cost more than
-- it protects.
BEGIN;

CREATE TABLE IF NOT EXISTS sync_log (
    sync_id       SERIAL PRIMARY KEY,
    sync_time     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    files_updated INTEGER,
    git_commit    TEXT
);

CREATE TABLE IF NOT EXISTS logs (
    id         integer PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    api_key_id integer NULL,
    action     text NOT NULL,
    type       text NOT NULL,
    created_at timestamptz DEFAULT now(),
    FOREIGN KEY (api_key_id) REFERENCES api_keys (id) ON UPDATE NO ACTION ON DELETE NO ACTION
);

CREATE TABLE IF NOT EXISTS state_configs (
    state TEXT PRIMARY KEY
);

-- Same seed as 100: one row per state that has jurisdictions.
INSERT INTO state_configs (state)
SELECT DISTINCT state FROM jurisdictions WHERE state IS NOT NULL
ON CONFLICT (state) DO NOTHING;

COMMIT;
