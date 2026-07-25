BEGIN;

-- Freshness is no longer a stored per-state cutoff. It's a rolling 90-day window computed
-- at query time (see database/freshness.py), so min_scraped_at has no readers left.
--
-- The knob it provided — raise a state's cutoff to invalidate its scrapes and launch a
-- re-scrape campaign — was used exactly once, by migration 101. The admin CRUD that would
-- have made it usable never shipped, and the stored value has been drifting ever since.
--
-- state_configs itself is deliberately KEPT, not dropped: it stays the home for per-state
-- settings so the next one is an ALTER rather than a new table. It is temporarily a bare
-- list of state codes carrying no settings — that is intentional, not an oversight.

ALTER TABLE state_configs DROP COLUMN min_scraped_at;

COMMIT;
