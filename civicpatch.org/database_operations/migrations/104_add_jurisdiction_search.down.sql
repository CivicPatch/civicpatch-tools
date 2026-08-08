BEGIN;

DROP INDEX IF EXISTS jurisdictions_search_text_trgm_idx;
DROP INDEX IF EXISTS jurisdictions_search_text_fts_idx;

ALTER TABLE jurisdictions DROP COLUMN IF EXISTS search_text;

-- pg_trgm is deliberately NOT dropped. The up uses CREATE EXTENSION IF NOT EXISTS, which
-- is a no-op when the extension already exists — so an unconditional DROP here would
-- remove something this migration never created. Leaving it costs nothing (an enabled
-- extension with no dependent objects is inert) and keeps the round-trip honest.

COMMIT;
