-- Reverses 228's structure. Values come back as each row's opened_at and the time of the
-- rollback; neither was recoverable once dropped.

BEGIN;

ALTER TABLE memberships ADD COLUMN IF NOT EXISTS last_seen_at timestamptz;
UPDATE memberships SET last_seen_at = opened_at WHERE last_seen_at IS NULL;
ALTER TABLE memberships ALTER COLUMN last_seen_at SET NOT NULL;
ALTER TABLE memberships ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

COMMIT;
