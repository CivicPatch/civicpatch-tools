BEGIN;

-- Restores the column and its epoch default (the shape migration 100 created).
--
-- The per-state VALUES are not recoverable: every state comes back at epoch, meaning
-- "nothing is stale", not whatever migration 101 or a later admin edit had set. Reversing
-- this migration therefore restores the structure, not the prior freshness state.

ALTER TABLE state_configs
    ADD COLUMN min_scraped_at TIMESTAMPTZ NOT NULL DEFAULT 'epoch'::timestamptz;

COMMIT;
