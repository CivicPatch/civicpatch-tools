-- Drops the constraint. The data changes are deliberately not reversed, for the reason 151
-- gives: a rollback that looks successful while restoring nothing is worse than one that
-- leaves the values in place.
--
-- The backfill filled `dismissed_reason` only where it was NULL and a `close_review` log
-- existed. After the fact those rows are indistinguishable from ones `dismiss_request` wrote
-- directly — it now writes both — so a down that NULLs every row matching its log would erase
-- reasons this migration never touched.
--
-- The `discarded` rows are likewise not restored: nothing writes that value any more, and
-- putting it back would immediately violate the constraint if the up were re-applied.
--
-- Neither is load-bearing. Readers treat a present reason as the answer either way, and a NULL
-- as unknown.

BEGIN;

ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_dismissed_reason_valid;

COMMIT;
