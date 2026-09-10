-- Explicit lineage for changesets, and a fourth kind for rollback to mint as.
--
-- `parent_changeset_id` — the changeset a new one layers on: whatever `live_roster_changeset`
-- (the changeset a roster edit belongs to — any kind except JURISDICTION_EDIT) returned at the
-- moment this one was minted. Computed once, at write time, instead of re-derived by every
-- reader — the same "store the answer instead of re-guessing it" as this whole plan's
-- assertions work.
--
-- `base_changeset_id` — set only on the two COLLECTION kinds (scrape, sheet_import): the newest
-- published collection changeset before this one. This is what a rollback's REBASE reads —
-- `proposed_roster` can only reconstruct a roster from a changeset with `source_records`, and
-- only collection kinds have any, so a `people_edit`/`jurisdiction_edit` changeset would answer
-- `[]` or worse if asked for its own base. Left NULL for those two kinds rather than inheriting
-- a value nothing reads.
--
-- Both `ON DELETE SET NULL`, same reasoning as `assertions.changeset_id` (188): provenance, not
-- identity.
--
-- `'rollback'` joins `kind`'s CHECK — a changeset in its own right (it publishes, it can be
-- undone, it needs an audit trail), deliberately excluded from `COLLECTION_KINDS` so
-- `advances_last_seen` never treats it as a sighting.

BEGIN;

ALTER TABLE changesets
    ADD COLUMN IF NOT EXISTS parent_changeset_id uuid REFERENCES changesets(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS base_changeset_id uuid REFERENCES changesets(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS changesets_parent_changeset_id_idx ON changesets (parent_changeset_id);
CREATE INDEX IF NOT EXISTS changesets_base_changeset_id_idx ON changesets (base_changeset_id);

ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_kind_check;
ALTER TABLE changesets ADD CONSTRAINT changesets_kind_check
    CHECK (kind IN ('scrape', 'sheet_import', 'people_edit', 'jurisdiction_edit', 'rollback'));

COMMIT;
