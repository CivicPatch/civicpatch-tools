-- The run columns leave `changesets`. Migration 169 moved the data; this removes the originals.
--
-- A changeset is now minted only by a run that succeeded (`people_collector._ingest_roster`), so
-- it can no longer be RUNNING or FAILED — those are states of an attempt, and the attempt has
-- its own table. `state` collapses from five values to three.
--
-- `changesets_scrape_has_a_run` goes with them: it tied `kind = 'scrape'` to a non-null status,
-- which was the constraint enforcing the merge that 147 made and this undoes.
--
-- `idx_changesets_status` disappears with its column.

BEGIN;

ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_scrape_has_a_run;

-- Generated from `status`, so it has to go before the column does.
ALTER TABLE changesets DROP COLUMN IF EXISTS state;

-- `arguments_json` goes too. A scrape's arguments are the run's, and 169 carried them there
-- (91 of 101 rows non-empty). A `jurisdiction_edit` stored its patch here, which is recorded
-- twice already: `change_logs` has the field diff and `jurisdictions.data` has the result.
ALTER TABLE changesets
    DROP COLUMN IF EXISTS status,
    DROP COLUMN IF EXISTS progress,
    DROP COLUMN IF EXISTS arguments_json;

ALTER TABLE changesets
    ADD COLUMN IF NOT EXISTS state text GENERATED ALWAYS AS (
        CASE
            WHEN published_at IS NOT NULL THEN 'published'
            WHEN dismissed_at IS NOT NULL THEN 'dismissed'
            ELSE 'ready'
        END
    ) STORED;

COMMIT;
