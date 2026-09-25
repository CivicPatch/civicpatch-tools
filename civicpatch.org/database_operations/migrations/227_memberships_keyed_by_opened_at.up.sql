-- Holding a post twice is two rows (plan step 15). `id` stays uuid5(person, post), the key
-- claims name, so the rows of one membership share it and the key becomes (id, opened_at).

BEGIN;

ALTER TABLE memberships DROP CONSTRAINT IF EXISTS memberships_pkey;
ALTER TABLE memberships ADD CONSTRAINT memberships_pkey PRIMARY KEY (id, opened_at);

COMMIT;
