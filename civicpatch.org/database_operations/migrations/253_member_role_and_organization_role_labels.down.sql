-- Reverses 253's schema. The re-keyed posts stay on `member`: the six-way split cannot be
-- recomputed from the rows, and every row already names the post it did.

BEGIN;

DROP FUNCTION IF EXISTS post_role_label(uuid, text);
ALTER TABLE organizations DROP COLUMN IF EXISTS extras_role_labels;

COMMIT;
