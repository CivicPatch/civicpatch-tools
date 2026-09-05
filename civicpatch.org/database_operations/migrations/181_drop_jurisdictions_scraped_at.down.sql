-- Restores the column, not its contents: it was a cache of a fact that is now derived, and
-- nothing re-stamps it. A rollback leaves it NULL everywhere, which reads as "never collected"
-- to the queries that used it — the safe direction, since that widens the scrape pool rather
-- than hiding jurisdictions from it.

BEGIN;

ALTER TABLE jurisdictions ADD COLUMN IF NOT EXISTS scraped_at timestamptz;

COMMIT;
