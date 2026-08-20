-- Reverses 122. `label` returns empty: the two arrays cannot be rejoined into the single
-- string it held without inventing a separator, and nothing read it, so restoring the column
-- is enough to make the schema match again.

BEGIN;

DROP INDEX IF EXISTS memberships_unmatched_text_idx;

ALTER TABLE memberships
    ADD COLUMN IF NOT EXISTS label text;

ALTER TABLE memberships
    DROP COLUMN IF EXISTS designations,
    DROP COLUMN IF EXISTS unmatched_text;

COMMIT;
