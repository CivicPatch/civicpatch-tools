-- The discriminator. `request_type` becomes `kind` and starts saying which producer made the
-- changeset, instead of which domain object it is about.
--
-- Today every row reads `people` — 400 of 400 on dev — and the producer is recovered from a
-- conjunction of two nullable columns that mean other things: `status` is the pipeline's
-- lifecycle, `batch_id` is "part of a bulk run". Provenance falls out of their intersection and
-- nothing enforces it. That is single-table inheritance with a discriminator one level too
-- coarse; every framework that implements STI makes the discriminator mandatory and exact,
-- because the alternative is inferring the subtype from which nullable columns happen to be set.
--
-- Four values, not three: changeset A (splitting jurisdiction edits into their own table) is
-- punted, so `jurisdiction_edit` stays a kind here rather than a table.
--
-- `changeset_batches.kind` loses its `state_` prefix in the same migration so the two columns
-- share one vocabulary. That is what lets the backfill *read* the batch's own answer instead of
-- inferring from `batch_id IS NOT NULL` — a rule that is true only while state scrapes do not
-- create batch rows, and would silently relabel every state scrape as an import the day they do.
BEGIN;

-- Batches first: the changeset backfill reads this column.
ALTER TABLE changeset_batches DROP CONSTRAINT IF EXISTS changeset_batches_kind_check;
UPDATE changeset_batches SET kind = 'scrape' WHERE kind = 'state_scrape';
ALTER TABLE changeset_batches ADD CONSTRAINT changeset_batches_kind_check
    CHECK (kind IN ('sheet_import', 'scrape'));

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'changesets'
                 AND column_name = 'request_type') THEN
        ALTER TABLE changesets RENAME COLUMN request_type TO kind;
    END IF;
END $$;

-- No default. The producer is never a fallback: a writer that does not say which one it is has
-- not been told to, and should fail rather than quietly become a scrape. Every `register_*`
-- function already passes a value.
ALTER TABLE changesets ALTER COLUMN kind DROP DEFAULT;

-- Idempotent by construction: on a second run nothing matches the old vocabulary, the batch
-- lookup returns the value already stored, and the status test reproduces its own answer.
UPDATE changesets c
   SET kind = CASE
       WHEN c.kind = 'jurisdiction_manual_edit' THEN 'jurisdiction_edit'
       ELSE COALESCE(
           (SELECT b.kind FROM changeset_batches b WHERE b.id = c.batch_id),
           CASE WHEN c.status IS NOT NULL THEN 'scrape' ELSE 'people_edit' END
       )
   END;

ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_kind_check;
ALTER TABLE changesets ADD CONSTRAINT changesets_kind_check
    CHECK (kind IN ('scrape', 'sheet_import', 'people_edit', 'jurisdiction_edit'));

-- The invariant nothing enforced before: only a scrape has a pipeline run behind it, and every
-- scrape has one. Verified against dev before adding — 95 of 95 scrapes carry a status, and
-- none of the other 305 rows do. Makes the nullable pipeline columns a *consequence* of the
-- kind rather than the only way to guess it.
ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_scrape_has_a_run;
ALTER TABLE changesets ADD CONSTRAINT changesets_scrape_has_a_run
    CHECK ((kind = 'scrape') = (status IS NOT NULL));

COMMIT;
