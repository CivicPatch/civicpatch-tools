BEGIN;

-- The contract half of 134, which was expand-only on purpose.
--
-- 134 split ten fields out of the `data` blob and backfilled them, verified identical across
-- all 20,712 rows. Every reader has since moved to the columns: `PERSON_JSON` assembles the
-- old shape from them, and the last blob read — the `office` fallback for people with no open
-- membership — now falls back to their most recently closed one instead.
--
-- `office` itself was never a column and is not becoming one. It is a view over memberships:
-- role and division live on the post, and the name is `source_labels` joined, which reproduced
-- `data->'office'` exactly for every person who has a membership at all.
ALTER TABLE people DROP COLUMN data;

-- Deliberately left off 134: a NOT NULL is not an expand-only change, and adding it there
-- broke every fixture that wrote the blob alone. It belongs here, with the blob gone and
-- `name` the only thing left that says who a row is about.
ALTER TABLE people ALTER COLUMN name SET NOT NULL;

COMMIT;
