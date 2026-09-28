-- Exactly reverses 231. The columns come back empty; a rebuild does not refill them.

BEGIN;

ALTER TABLE memberships ADD COLUMN IF NOT EXISTS designations text[] NOT NULL DEFAULT '{}'::text[];
ALTER TABLE memberships ADD COLUMN IF NOT EXISTS meta_unmatched_text text[] NOT NULL DEFAULT '{}'::text[];
CREATE INDEX IF NOT EXISTS memberships_meta_unmatched_text_idx ON memberships USING gin (meta_unmatched_text);

COMMIT;
