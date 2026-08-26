-- Lossy, and honestly so: the up dropped the column without copying it anywhere, because it
-- held nothing the derivation does not reproduce. The column comes back empty rather than
-- carrying the 11,763 copies it used to.
--
-- Backfilling here is not possible in SQL: `derive_post_label` composes a division label from
-- an ocdid, which is Python. Anything that needs the old values must recompute them.
BEGIN;

ALTER TABLE posts ADD COLUMN IF NOT EXISTS label text;

COMMIT;
