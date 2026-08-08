BEGIN;

-- Jurisdiction search, step 1 (plan: .scratch/2026-08-07-plan-jurisdiction-search.md).
-- Lands the structure for nationwide "seattle wa" / "seattle washington" search. Inert
-- on day one: nothing queries these until the search endpoint ships.
--
-- search_text is one denormalised blob per row holding everything the row should be
-- findable by — official name, friendly display name, state code, state name:
--
--     "seattle city seattle wa washington"
--
-- so a query's tokens can all be required to appear without parsing the query for a
-- state qualifier. It cannot be a generated column: the state name lives in a *different*
-- row (level='state'), and GENERATED ALWAYS AS may only reference its own row. The sync
-- path owns keeping it correct.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- NOT NULL DEFAULT '' is deliberate. A NULL search_text matches nothing, so a write path
-- that forgets to set it makes rows silently unsearchable — no error, just absent
-- results. The constraint turns that into a loud failure instead.
ALTER TABLE jurisdictions ADD COLUMN IF NOT EXISTS search_text TEXT NOT NULL DEFAULT '';

-- Backfill before the indexes exist: writing to an indexed column maintains both GINs
-- row by row, where building them afterwards does the work once.
--
-- concat_ws skips NULLs, so this degrades cleanly on the two fields that do not exist
-- yet — display_name (a new open-data field) and the level='state' rows (not yet
-- synced). Without them a row is still findable as "seattle city wa"; the fuller forms
-- start working when that data lands, with no migration needed, just a re-derive.
UPDATE jurisdictions j SET search_text = lower(concat_ws(' ',
    j.data->>'name',
    j.data->>'display_name',
    j.state,
    (SELECT s.data->>'name' FROM jurisdictions s
      WHERE s.level = 'state' AND s.state = j.state)
));

-- Tier 1 — token-AND with prefix, e.g. to_tsquery('simple', 'seattle:* & wa:*').
-- 'simple' and never 'english': stemming mangles proper nouns (Reading -> read).
-- Queries MUST use this identical two-argument form. The one-argument to_tsvector()
-- resolves against the default_text_search_config GUC, fails to match this expression,
-- and silently falls back to a sequential scan.
CREATE INDEX IF NOT EXISTS jurisdictions_search_text_fts_idx
ON jurisdictions USING GIN (to_tsvector('simple', search_text));

-- Tier 2 — trigram fallback for typos ("seatle wa"), consulted only when tier 1 comes up
-- short. Also what makes unanchored LIKE '%york%' cheap, which the existing btree on
-- LOWER(data->>'name') cannot serve.
CREATE INDEX IF NOT EXISTS jurisdictions_search_text_trgm_idx
ON jurisdictions USING GIN (search_text gin_trgm_ops);

COMMIT;
