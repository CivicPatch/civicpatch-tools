-- Assertions become append-only.
--
-- Today's upsert overwrites `value`, `sources`, `asserted_by`, `asserted_at` in place on every
-- re-assert, which destroys attribution: a claim Alice made is silently re-stamped to whoever
-- asserts that field next. It also means a rollback can only ever fall back to the scrape,
-- never to an earlier human judgement, because that judgement's row no longer exists.
--
-- From here, a row is never rewritten after insert. "What currently applies" is derived by
-- reading — see `database/assertions.py::asserted_values` — not enforced by a unique index, so
-- both partial indexes that made a repeat assert an UPDATE have to go: history means several
-- rows can exist for one (entity, field), which those indexes exist specifically to prevent.
--
-- Retracting a claim stamps it withdrawn rather than deleting it, for the same reason: deleting
-- would destroy the one copy of a human's original judgement, and it is not the only human
-- action recorded here that gets to keep its evidence.
--
-- ⚠️ This migration's `.down.sql` will fail once a second row exists for any (entity, field) —
-- i.e. within minutes of real use, the first time an already-asserted field is asserted again.
-- Both dropped indexes require exactly one row per key; they cannot be recreated over a table
-- that, by design, now holds several. Take a database dump before applying this in a database
-- that matters — the dump is the real rollback path, not this file.

BEGIN;

ALTER TABLE assertions
    ADD COLUMN IF NOT EXISTS withdrawn_at timestamptz,
    ADD COLUMN IF NOT EXISTS withdrawn_by uuid REFERENCES users(id),
    ADD COLUMN IF NOT EXISTS withdrawn_reason text;

ALTER TABLE assertions DROP CONSTRAINT IF EXISTS assertions_withdrawn_together;
ALTER TABLE assertions ADD CONSTRAINT assertions_withdrawn_together
    CHECK ((withdrawn_at IS NULL) = (withdrawn_by IS NULL));

DROP INDEX IF EXISTS assertions_one_accept_per_scalar_field;
DROP INDEX IF EXISTS assertions_one_row_per_value;

-- Widened with field_path: this is now the index the fold reads through, keyed exactly the way
-- `asserted_values` groups (entity_type, entity_id, field_path), newest first.
DROP INDEX IF EXISTS assertions_entity_idx;
CREATE INDEX IF NOT EXISTS assertions_entity_idx
    ON assertions (entity_type, entity_id, field_path, asserted_at DESC);

COMMIT;
