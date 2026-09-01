-- "What happened to this scrape" becomes a real query, so give it an index.
--
-- `change_logs` is the history: append-only, immutable, one row per event, with who and when.
-- `changesets` is current state — overwritten in place, so it can say where a scrape ended up
-- but never what happened along the way.
--
-- Until now only three of the six terminal events wrote a row at all, and nothing read the
-- table by changeset. Both change together: every dismissal now logs a `close_review` carrying
-- its reason in the payload, and this index makes reading a single scrape's history cheap.
--
-- Existing indexes cover the other two access patterns — `created_at DESC` for the activity
-- feed, `jurisdiction_ocdid` for a place's timeline. Neither helps here.
--
-- Not partitioned, deliberately. At 738 bytes a row and ~9,500 active jurisdictions, even a
-- weekly scrape where *nothing* ever published is ~365 MB/year, and the realistic figure is a
-- fraction of that. Time-partitioning `created_at` is the lever if this ever reaches hundreds
-- of millions of rows; it is not worth the complexity now.
BEGIN;

CREATE INDEX IF NOT EXISTS idx_change_logs_changeset_id
    ON change_logs (changeset_id)
    WHERE changeset_id IS NOT NULL;

COMMIT;
