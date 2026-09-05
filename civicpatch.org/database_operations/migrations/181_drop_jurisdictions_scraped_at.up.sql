-- `jurisdictions.scraped_at` goes. Freshness derives from published collection changesets now.
--
-- It never meant what it said. `_record_publish` stamped it on **every** publish with no
-- filter, so measured 2026-09-05: 60 sheet imports, 58 scrapes and **10 hand edits** had all
-- set it, and 25 of 64 published jurisdictions disagreed with `max(created_at)` over their own
-- changesets. Not drift — last-writer-wins over a column whose name promised something
-- narrower.
--
-- The correct rule already existed twice and reached neither the column nor the live path:
-- `jurisdictions.stamp_scraped_at` guarded on "the changeset has a run" and had **zero
-- callers**, while `publish_request` computed `advances_last_seen` a few lines above the stamp
-- and used it to stop a hand edit dating `memberships.last_seen_at`. One transaction, the same
-- question asked, honoured for memberships and ignored here.
--
-- Replaced by `LAST_COLLECTED_JOIN`: `max(updated_at)` over published changesets of a
-- collection kind. `updated_at` because that is when the content was confirmed — the key
-- superseding already orders on — and collection kinds because a hand edit reads no source.
--
-- ⚠ **"Stale" changes meaning.** A jurisdiction kept fresh by a hand edit is stale again, and
-- re-enters the scrape pool. That is the point, and it is a behaviour change to the thing that
-- decides what gets scraped.
--
-- The parquet `jurisdictions.scraped_at` column is dropped with it rather than renamed
-- (Mango-chan, 2026-09-05) — it never meant what it said there either.

BEGIN;

ALTER TABLE jurisdictions DROP COLUMN IF EXISTS scraped_at;

COMMIT;
