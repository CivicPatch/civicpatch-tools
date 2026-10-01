BEGIN;

ALTER TABLE posts ADD COLUMN IF NOT EXISTS meta_headcount integer NOT NULL DEFAULT 1;
ALTER TABLE posts ADD COLUMN IF NOT EXISTS meta_is_tracked boolean NOT NULL DEFAULT true;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'posts_headcount_check') THEN
        ALTER TABLE posts ADD CONSTRAINT posts_headcount_check CHECK (meta_headcount > 0);
    END IF;
END
$$;

-- Refilled from each post's newest live accept claim; the dropped unclaimed values are gone.
UPDATE posts SET meta_headcount = (latest.value #>> '{}')::integer
FROM (
    SELECT DISTINCT ON (entity_id) entity_id, value
    FROM claims
    WHERE entity_type = 'post' AND field_path = 'meta_headcount' AND kind = 'accept'
      AND claim_is_live(id)
    ORDER BY entity_id, created_at DESC
) latest
WHERE posts.id = latest.entity_id;

UPDATE posts SET meta_is_tracked = (latest.value #>> '{}')::boolean
FROM (
    SELECT DISTINCT ON (entity_id) entity_id, value
    FROM claims
    WHERE entity_type = 'post' AND field_path = 'meta_is_tracked' AND kind = 'accept'
      AND claim_is_live(id)
    ORDER BY entity_id, created_at DESC
) latest
WHERE posts.id = latest.entity_id;

COMMIT;
