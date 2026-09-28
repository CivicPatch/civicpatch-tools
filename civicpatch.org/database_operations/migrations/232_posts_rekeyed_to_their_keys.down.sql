-- Reverses 232's schema. The re-keyed ids stay: the old ones were hashed from division ids 230
-- renamed, so they cannot be recomputed, and every row already names the post it did.

BEGIN;

ALTER TABLE posts DROP CONSTRAINT IF EXISTS posts_id_is_its_key;
ALTER TABLE posts ALTER COLUMN id SET DEFAULT gen_random_uuid();
DROP FUNCTION IF EXISTS post_id_of_key(uuid, text, text);

COMMIT;
