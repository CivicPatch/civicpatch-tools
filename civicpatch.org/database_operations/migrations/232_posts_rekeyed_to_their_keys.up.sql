-- A post's id is uuid5 of (organization, role, division), PostKey.post_id. 230 renamed divisions
-- in place, so those posts kept ids hashed from the old key; re-key them, then refuse any drift.

BEGIN;

-- The database's copy of core/projection/facts.py::PostKey.post_id; the two must agree.
CREATE OR REPLACE FUNCTION post_id_of_key(organization_id uuid, role_id text, division_ocdid text)
RETURNS uuid LANGUAGE sql IMMUTABLE AS $$
    SELECT uuid_generate_v5(
        'c8374c67-da4d-4aac-a0d9-4f353c803eca'::uuid,
        organization_id::text || '|' || role_id || '|' || division_ocdid
    )
$$;

CREATE TEMP TABLE post_rekeys ON COMMIT DROP AS
SELECT id AS old_id, post_id_of_key(organization_id, role_id, division_ocdid) AS new_id, jurisdiction_ocdid
FROM posts
WHERE id <> post_id_of_key(organization_id, role_id, division_ocdid);

-- A membership's id is uuid5 of (person, post), shared/utils/membership_ids.py. Every person in the
-- jurisdiction, since a claim may name a membership that has no row.
CREATE TEMP TABLE membership_rekeys ON COMMIT DROP AS
SELECT uuid_generate_v5('5364ee76-7dec-41fd-a3b0-7218a73ea92f'::uuid, pe.id::text || '|' || r.old_id::text) AS old_id,
       uuid_generate_v5('5364ee76-7dec-41fd-a3b0-7218a73ea92f'::uuid, pe.id::text || '|' || r.new_id::text) AS new_id
FROM post_rekeys r
JOIN people pe ON pe.jurisdiction_ocdid = r.jurisdiction_ocdid;

-- memberships.post_id follows through its ON UPDATE CASCADE foreign keys.
UPDATE posts SET id = r.new_id FROM post_rekeys r WHERE posts.id = r.old_id;

UPDATE memberships SET id = r.new_id FROM membership_rekeys r WHERE memberships.id = r.old_id;

UPDATE claims SET value = to_jsonb(r.new_id::text)
FROM post_rekeys r
WHERE claims.entity_type = 'person' AND claims.field_path = 'posts'
  AND claims.value #>> '{}' = r.old_id::text;

UPDATE claims SET entity_id = r.new_id
FROM membership_rekeys r
WHERE claims.entity_type = 'membership' AND claims.entity_id = r.old_id;

-- From here a post's id cannot drift from its key: a rename has to re-key, or it fails.
ALTER TABLE posts ALTER COLUMN id DROP DEFAULT;
ALTER TABLE posts DROP CONSTRAINT IF EXISTS posts_id_is_its_key;
ALTER TABLE posts ADD CONSTRAINT posts_id_is_its_key
    CHECK (id = post_id_of_key(organization_id, role_id, division_ocdid));

COMMIT;
