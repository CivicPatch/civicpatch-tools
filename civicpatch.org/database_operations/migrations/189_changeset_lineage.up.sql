-- Explicit lineage for changesets, and a fourth kind for rollback to mint as.
--
-- `parent_changeset_id` — the changeset a new one layers on: whatever `live_roster_changeset`
-- (the changeset a roster edit belongs to — any kind except JURISDICTION_EDIT) returned at the
-- moment this one was minted. Computed once, at write time, instead of re-derived by every
-- reader — the same "store the answer instead of re-guessing it" as this whole plan's
-- assertions work.
--
-- `ON DELETE SET NULL`, same reasoning as `assertions.changeset_id` (188): provenance, not
-- identity.
--
-- `'rollback'` joins `kind`'s CHECK — a changeset in its own right (it publishes, it can be
-- undone, it needs an audit trail), deliberately excluded from `COLLECTION_KINDS` so
-- `advances_last_seen` never treats it as a sighting.
--
-- No `base_changeset_id` here: an earlier draft of this migration added one, for a rollback
-- "rebase" (reconstruct a scrape/import's roster from an earlier collection changeset's
-- `source_records`) that never got built — rollback ended up scoped to withdrawing individual
-- assertions, grouped by jurisdiction at execute time, never a changeset-level target. Cut
-- before this migration ever shipped rather than added-then-dropped later.

BEGIN;

ALTER TABLE changesets
    ADD COLUMN IF NOT EXISTS parent_changeset_id uuid REFERENCES changesets(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS changesets_parent_changeset_id_idx ON changesets (parent_changeset_id);

ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_kind_check;
ALTER TABLE changesets ADD CONSTRAINT changesets_kind_check
    CHECK (kind IN ('scrape', 'sheet_import', 'people_edit', 'jurisdiction_edit', 'rollback'));

COMMIT;
