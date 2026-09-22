BEGIN;

-- A claim about a membership names the membership: `membership_id(person, post)`, the id the
-- fold computes, where `post` is the fold's `post_key_id`, never today's random `posts.id`.
-- Every live claim of the old shapes is copied into that shape. The originals stay, because
-- today's publish still reads them until the fold replaces it.
--
-- Temporary functions, gone when the migration's connection closes: nothing is left in the
-- database. The deploy that switches publish to the fold repeats the copy the same way, to
-- pick up whatever the old routes filed in between; rerunning finds the copies already made.

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

CREATE OR REPLACE FUNCTION pg_temp.copy_membership_claims() RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    copied integer;
BEGIN
WITH old AS (
    -- Each old claim as (person, today's post, field, kind, value). A NULL value means "the
    -- post's id", which is what an `exists` claim carries.

    -- A picked post.
    SELECT a.id, a.entity_id AS person_id, a.value #>> '{}' AS post_ref,
           'exists' AS field_path, 'accept' AS kind, NULL::jsonb AS value
    FROM assertions a
    WHERE a.entity_type = 'person' AND a.field_path = 'post_id' AND a.kind = 'accept'

    UNION ALL
    -- Keyed on a `memberships` row. A close becomes a reject: one yes/no per membership.
    SELECT a.id, m.person_id, m.post_id::text,
           CASE WHEN a.field_path = 'closed_at' THEN 'exists' ELSE a.field_path END,
           CASE WHEN a.field_path = 'closed_at' THEN 'reject' ELSE a.kind END,
           CASE WHEN a.field_path IN ('exists', 'closed_at') THEN NULL ELSE a.value END
    FROM assertions a
    JOIN memberships m ON m.id = a.entity_id
    WHERE a.entity_type = 'membership'

    UNION ALL
    -- "Not a member of anything here": a reject on each membership they have had.
    SELECT a.id, a.entity_id, m.post_id::text, 'exists', 'reject', NULL
    FROM assertions a
    JOIN memberships m ON m.person_id = a.entity_id
    WHERE a.entity_type = 'person' AND a.field_path = 'exists' AND a.kind = 'reject'

    UNION ALL
    -- Term dates typed on the person, onto their open membership, else their latest.
    SELECT a.id, a.entity_id, latest.post_id::text, a.field_path, a.kind, a.value
    FROM assertions a
    JOIN LATERAL (
        SELECT m.post_id FROM memberships m
         WHERE m.person_id = a.entity_id
         ORDER BY (m.closed_at IS NULL) DESC, m.first_seen_at DESC
         LIMIT 1
    ) latest ON true
    WHERE a.entity_type = 'person' AND a.field_path IN ('start_date', 'end_date')
),
restated AS (
    SELECT DISTINCT
           pg_temp.membership_id(old.person_id, fold.post_id) AS entity_id,
           old.field_path, old.kind,
           coalesce(old.value, to_jsonb(fold.post_id::text)) AS value,
           original.created_by, original.created_at, original.changeset_id, original.sources
    FROM old
    JOIN assertions original ON original.id = old.id
    JOIN posts p ON p.id::text = old.post_ref
    CROSS JOIN LATERAL (
        SELECT pg_temp.post_key_id(p.organization_id, p.role_id, p.division_ocdid) AS post_id
    ) fold
    WHERE original.withdrawn_at IS NULL
)
INSERT INTO assertions
    (entity_type, entity_id, field_path, kind, value, created_by, created_at, changeset_id,
     sources)
SELECT 'membership', r.entity_id, r.field_path, r.kind, r.value, r.created_by, r.created_at,
       r.changeset_id, r.sources
FROM restated r
WHERE NOT EXISTS (
    SELECT 1 FROM assertions existing
     WHERE existing.entity_type = 'membership' AND existing.entity_id = r.entity_id
       AND existing.field_path = r.field_path AND existing.kind = r.kind
       AND existing.value = r.value AND existing.created_at = r.created_at
);
GET DIAGNOSTICS copied = ROW_COUNT;
RETURN copied;
END;
$$;

SELECT pg_temp.copy_membership_claims();

COMMIT;
