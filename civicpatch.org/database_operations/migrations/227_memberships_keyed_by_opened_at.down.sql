-- Reverses 227. Refuses while any membership has more than one row: `id` alone cannot key them.

BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM memberships GROUP BY id HAVING count(*) > 1) THEN
        RAISE EXCEPTION 'memberships with several rows; id alone cannot be the key';
    END IF;
END $$;

ALTER TABLE memberships DROP CONSTRAINT IF EXISTS memberships_pkey;
ALTER TABLE memberships ADD CONSTRAINT memberships_pkey PRIMARY KEY (id);

COMMIT;
