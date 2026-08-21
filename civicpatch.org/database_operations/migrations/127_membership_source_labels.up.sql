BEGIN;

-- What the source called this post, as the labels it was joined from — `parsed.labels`, which
-- is `office.name` split on " - ". Stored as the parts rather than the rendering, so nothing
-- downstream has to re-split, and so triage can show the one label a term came out of instead
-- of the whole concatenation.
--
-- No FK to `source_records`: a membership outlives the evidence that produced it, source
-- records cascade from requests, and one membership is produced by many of them over time.
-- Written in the same statement as `unmatched_text`, so the term and the labels it came from
-- cannot disagree — a read-time join can, because source records land at ingest while
-- memberships are written at publish.
--
-- Plural and `source_`-prefixed to stay clear of `label`, which is singular and human-owned.
ALTER TABLE memberships ADD COLUMN source_labels text[] NOT NULL DEFAULT '{}';

COMMIT;
