-- The published side of `changesets`, for the aggregate that replaces `jurisdictions.scraped_at`.
--
-- `idx_changesets_pending_by_jurisdiction` covers the other half — it is partial on
-- `published_at IS NULL`, exactly the rows this scan skips. `LAST_COLLECTED_JOIN` groups every
-- published collection changeset by jurisdiction and takes `max(updated_at)`.

BEGIN;

CREATE INDEX IF NOT EXISTS idx_changesets_published_by_jurisdiction
    ON changesets (jurisdiction_ocdid, updated_at DESC)
    WHERE published_at IS NOT NULL;

COMMIT;
