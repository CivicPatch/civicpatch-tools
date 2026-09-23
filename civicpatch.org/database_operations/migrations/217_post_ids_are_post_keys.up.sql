BEGIN;

-- A post's id becomes `uuid5` over its key, and every claim about a membership is restated to
-- name it the way the fold reads one. Three sections in one transaction, in this order because
-- each joins `posts` as the section before it left the table. Nothing here is DDL except the
-- foreign key section 2 needs, and every section is rerunnable on its own terms.

-- 1. Holding a post becomes a claim about the person.

-- A membership's row id is minted by the projection, which deletes and rewrites it on every
-- publish, so no claim can name one and survive. Which posts somebody holds moves onto the
-- person as a `posts` claim, one per post, valued by the post's id — the one thing about a
-- membership that is not derived. What a membership is *called*, and when it ran, stays a
-- claim about the membership, keyed `membership_id(person, post)` the way the fold reads it.
--
-- Joins `posts` while its ids are still the random ones these claims were written against, so
-- it runs before section 2 and writes the id that section is about to mint.
--
-- Temporary functions only (`pg_temp.`), gone when the migration's connection closes: nothing
-- is left in the database for anyone to maintain. `test_id_functions.py` pins their encodings
-- against the Python that computes the same ids.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Twins of `PostKey.post_id` and `shared.utils.membership_ids.membership_id`; a test pins the
-- encodings against the Python.
CREATE OR REPLACE FUNCTION pg_temp.post_key_id(organization_id uuid, role_id text, division_ocdid text)
RETURNS uuid LANGUAGE sql IMMUTABLE AS $$
    SELECT uuid_generate_v5(
        'c8374c67-da4d-4aac-a0d9-4f353c803eca'::uuid,
        organization_id::text || '|' || role_id || '|' || division_ocdid
    )
$$;

CREATE OR REPLACE FUNCTION pg_temp.membership_id(person_id uuid, post_id uuid)
RETURNS uuid LANGUAGE sql IMMUTABLE AS $$
    SELECT uuid_generate_v5(
        '5364ee76-7dec-41fd-a3b0-7218a73ea92f'::uuid,
        person_id::text || '|' || post_id::text
    )
$$;

-- 216 copied every membership claim to a key hashed from the post's key. The existence copies
-- cannot be decoded back to a post, and the originals can (they name a `memberships` row), so
-- the copies go and the originals are rewritten below.
DELETE FROM assertions a
 WHERE a.entity_type = 'membership'
   AND a.field_path IN ('exists', 'closed_at', 'post_id')
   AND NOT EXISTS (SELECT 1 FROM memberships m WHERE m.id = a.entity_id);

-- The label and date copies are already keyed the way the fold reads them, but it is the
-- original a withdrawal points at, so the copy goes and the original is re-keyed.
DELETE FROM assertions duplicate
 WHERE duplicate.entity_type = 'membership'
   AND duplicate.field_path IN ('label', 'start_date', 'end_date')
   AND NOT EXISTS (SELECT 1 FROM memberships m WHERE m.id = duplicate.entity_id)
   AND EXISTS (
       SELECT 1 FROM assertions original
        WHERE original.entity_type = 'membership'
          AND original.field_path = duplicate.field_path AND original.kind = duplicate.kind
          AND original.value = duplicate.value AND original.created_by = duplicate.created_by
          AND original.created_at = duplicate.created_at
          AND EXISTS (SELECT 1 FROM memberships m WHERE m.id = original.entity_id)
   );

UPDATE assertions a
   SET entity_id = pg_temp.membership_id(
           m.person_id, pg_temp.post_key_id(p.organization_id, p.role_id, p.division_ocdid)
       )
  FROM memberships m
  JOIN posts p ON p.id = m.post_id
 WHERE a.entity_type = 'membership' AND a.entity_id = m.id
   AND a.field_path IN ('label', 'start_date', 'end_date');

-- Every claim that said whether a membership exists, of each shape it was ever written in.
-- A close becomes a reject: one yes/no per membership, and "they left" and "the page was
-- wrong" end it the same way. Withdrawn rows convert too — the shape changes, not the
-- liveness, and the withdrawals that point at them keep pointing at the same row.
UPDATE assertions a
   SET entity_type = 'person',
       entity_id = m.person_id,
       field_path = 'posts',
       kind = CASE WHEN a.field_path = 'closed_at' THEN 'reject' ELSE a.kind END,
       value = to_jsonb(
           pg_temp.post_key_id(p.organization_id, p.role_id, p.division_ocdid)::text
       )
  FROM memberships m
  JOIN posts p ON p.id = m.post_id
 WHERE a.entity_type = 'membership' AND a.entity_id = m.id
   AND a.field_path IN ('exists', 'closed_at');

-- A picked post said the same thing in the person's own claims.
UPDATE assertions a
   SET field_path = 'posts',
       value = to_jsonb(
           pg_temp.post_key_id(p.organization_id, p.role_id, p.division_ocdid)::text
       )
  FROM posts p
 WHERE a.entity_type = 'person' AND a.field_path = 'post_id'
   AND p.id::text = a.value #>> '{}';

-- "Not a member of anything here": a reject of each post they hold. The person's own claim
-- keeps its meaning — section 3 withdraws the records behind it — so this one is a copy.
-- Rerunning finds the rejects it already made.
INSERT INTO assertions
    (entity_type, entity_id, field_path, kind, value, created_by, created_at, changeset_id,
     sources)
SELECT 'person', a.entity_id, 'posts', 'reject',
       to_jsonb(pg_temp.post_key_id(p.organization_id, p.role_id, p.division_ocdid)::text),
       a.created_by, a.created_at, a.changeset_id, a.sources
FROM assertions a
JOIN memberships m ON m.person_id = a.entity_id
JOIN posts p ON p.id = m.post_id
WHERE a.entity_type = 'person' AND a.field_path = 'exists' AND a.kind = 'reject'
  AND a.withdrawn_at IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM assertions existing
       WHERE existing.entity_type = 'person' AND existing.entity_id = a.entity_id
         AND existing.field_path = 'posts' AND existing.kind = 'reject'
         AND existing.value = to_jsonb(
             pg_temp.post_key_id(p.organization_id, p.role_id, p.division_ocdid)::text
         )
  );


-- 2. A post's id becomes `post_key_id(organization, role, division)`.

-- A post's id is `post_key_id(organization, role, division)`, the id the fold computes, so the
-- row, the fold and every claim name a post the same way. Everything holding a post id moves
-- with it: memberships by cascade, claims and activity by the mapping below.
--
-- A temporary function, gone when the migration's connection closes: nothing is left in the
-- database. Rerunning maps nothing, since every id already equals its key.

-- `pg_temp.post_key_id` is section 1's, and the connection is the same one.
DROP TABLE IF EXISTS post_id_map;
CREATE TEMP TABLE IF NOT EXISTS post_id_map ON COMMIT DROP AS
SELECT id AS old_id, pg_temp.post_key_id(organization_id, role_id, division_ocdid) AS new_id
FROM posts
WHERE id <> pg_temp.post_key_id(organization_id, role_id, division_ocdid);

-- The composite key already cascades; the plain one would block the update below.
ALTER TABLE memberships DROP CONSTRAINT IF EXISTS memberships_post_id_fkey;
ALTER TABLE memberships ADD CONSTRAINT memberships_post_id_fkey
    FOREIGN KEY (post_id) REFERENCES posts(id) ON UPDATE CASCADE;

UPDATE posts p SET id = m.new_id FROM post_id_map m WHERE p.id = m.old_id;

-- Claims about a post: label, headcount, tracked.
UPDATE assertions a SET entity_id = m.new_id
FROM post_id_map m
WHERE a.entity_type = 'post' AND a.entity_id = m.old_id;

-- Activity names a post as a change's entity, or as a membership move's before and after.
UPDATE activity a SET changes = jsonb_set(a.changes, '{entity_id}', to_jsonb(m.new_id::text))
FROM post_id_map m
WHERE a.changes ->> 'entity_type' = 'post' AND a.changes ->> 'entity_id' = m.old_id::text;

UPDATE activity a SET changes = jsonb_set(a.changes, '{fields}', moved.fields)
FROM (
    SELECT a2.id,
           jsonb_agg(
               CASE WHEN f ->> 'field' = 'post_id' THEN f || jsonb_build_object(
                   'before', coalesce(to_jsonb(before_map.new_id::text), f -> 'before'),
                   'after', coalesce(to_jsonb(after_map.new_id::text), f -> 'after')
               ) ELSE f END
               ORDER BY position
           ) AS fields
    FROM activity a2
    CROSS JOIN LATERAL jsonb_array_elements(a2.changes -> 'fields') WITH ORDINALITY AS e(f, position)
    LEFT JOIN post_id_map before_map ON before_map.old_id::text = f ->> 'before'
    LEFT JOIN post_id_map after_map ON after_map.old_id::text = f ->> 'after'
    WHERE jsonb_typeof(a2.changes -> 'fields') = 'array'
    GROUP BY a2.id
    HAVING bool_or(before_map.old_id IS NOT NULL OR after_map.old_id IS NOT NULL)
) moved
WHERE a.id = moved.id;

DROP TABLE IF EXISTS post_id_map;


-- 3. "Not a member of anything here" becomes a withdrawal of the records.

-- A person-level `exists` reject meant "not a member of anything here": never held, not left.
-- 216 copied each into a membership reject, which from deploy B lasts only until the
-- organization is read again. What the reviewer meant is a withdrawal of the records that put
-- the person there, so this files one, under one `rollback` changeset per rejecting user and
-- jurisdiction, dated at the reject. Rerunning finds the rows it already made.

INSERT INTO changesets
    (id, kind, jurisdiction_ocdid, created_by_user_id, resolved_by_user_id,
     created_at, published_at, updated_at, comment)
SELECT md5('219:' || a.created_by::text || ':' || p.jurisdiction_ocdid)::uuid,
       'rollback', p.jurisdiction_ocdid, a.created_by, a.created_by,
       min(a.created_at), min(a.created_at), min(a.created_at),
       'migration 219: "not a member of anything here" withdraws the records'
FROM assertions a
JOIN people p ON p.id = a.entity_id
WHERE a.entity_type = 'person' AND a.field_path = 'exists' AND a.kind = 'reject'
  AND a.withdrawn_at IS NULL
GROUP BY a.created_by, p.jurisdiction_ocdid
ON CONFLICT (id) DO NOTHING;

INSERT INTO assertions
    (entity_type, entity_id, field_path, kind, value, created_by, created_at, changeset_id)
SELECT 'source_record', s.id, NULL, 'withdraw', 'null'::jsonb, a.created_by, a.created_at,
       md5('219:' || a.created_by::text || ':' || p.jurisdiction_ocdid)::uuid
FROM assertions a
JOIN people p ON p.id = a.entity_id
JOIN source_record_identities i ON i.person_id = a.entity_id
JOIN source_records s ON s.id = i.source_record_id
WHERE a.entity_type = 'person' AND a.field_path = 'exists' AND a.kind = 'reject'
  AND a.withdrawn_at IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM assertions w
       WHERE w.kind = 'withdraw' AND w.entity_type = 'source_record' AND w.entity_id = s.id
  );


COMMIT;
