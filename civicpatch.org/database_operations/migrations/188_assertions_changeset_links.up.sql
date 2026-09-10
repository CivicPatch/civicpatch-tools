-- The two joins a rollback needs, per the plan's assertion-immutability design.
--
-- `changeset_id` — which changeset CREATED a claim. Write-once in practice (nothing ever
-- updates it after insert; assertions are append-only since 187), so it can answer "everything
-- this changeset asserted" without re-deriving it. Nullable: a field asserted directly (the
-- `POST /assertions` endpoint) or via a post/membership edit outside any review has no
-- changeset to name.
--
-- `withdrawn_by_changeset_id` — the symmetric half, which rollback changeset WITHDREW a claim.
-- What turns "roll back this account" into an undoable UNIT: `RESTORE WHERE
-- withdrawn_by_changeset_id = X` reverses one rollback wholesale, rather than requiring a
-- moderator to find and restore each row it touched.
--
-- Both backfill NULL — nothing before this migration can be attributed to a changeset, and that
-- is honest: the upsert they were written under overwrote `asserted_by` on every re-assert, so
-- pre-187 rows already can't support "who did this" reliably either.
--
-- ON DELETE SET NULL, matching `pipeline_runs.changeset_id` (169): the same precedent for the
-- same reason — this is provenance, not identity, and losing the breadcrumb is a far smaller
-- problem than a changeset becoming impossible to delete because some assertion still points
-- at it. Nothing in this codebase deletes a published changeset today, but test fixtures do
-- clean up sentinel changesets, and the default RESTRICT broke that: `_wipe()` helpers across
-- the suite delete changesets before the assertions pointing at them, and a hard FK made every
-- one of those a foreign-key violation.

BEGIN;

ALTER TABLE assertions
    ADD COLUMN IF NOT EXISTS changeset_id uuid REFERENCES changesets(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS withdrawn_by_changeset_id uuid REFERENCES changesets(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS assertions_changeset_id_idx ON assertions (changeset_id);
CREATE INDEX IF NOT EXISTS assertions_withdrawn_by_changeset_id_idx
    ON assertions (withdrawn_by_changeset_id);

COMMIT;
