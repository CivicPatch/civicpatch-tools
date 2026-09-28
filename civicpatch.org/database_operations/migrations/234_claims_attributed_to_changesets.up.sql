-- Claims filed with no changeset (mostly 6-18 Sept publish mints, kept on purpose 2026-09-27) get
-- one: a born-published roster_edit per (user, jurisdiction), dated at its first claim, so the
-- loader needs no second rule for them and rollback can reach them.

BEGIN;

CREATE TEMP TABLE unattributed ON COMMIT DROP AS
SELECT c.id, c.created_by, c.created_at,
       CASE c.entity_type
           WHEN 'person' THEN COALESCE(
               (SELECT pe.jurisdiction_ocdid FROM people pe WHERE pe.id = c.entity_id),
               (SELECT sr.jurisdiction_ocdid FROM source_records sr WHERE sr.person_id = c.entity_id LIMIT 1))
           WHEN 'post' THEN (SELECT p.jurisdiction_ocdid FROM posts p WHERE p.id = c.entity_id)
           WHEN 'source_record' THEN (SELECT sr.jurisdiction_ocdid FROM source_records sr WHERE sr.id = c.entity_id)
           WHEN 'membership' THEN COALESCE(
               (SELECT p.jurisdiction_ocdid FROM memberships m JOIN posts p ON p.id = m.post_id
                 WHERE m.id = c.entity_id LIMIT 1),
               -- A membership id is uuid5(person, post); a claim may name one with no row.
               (SELECT p.jurisdiction_ocdid FROM people pe
                  JOIN posts p ON p.jurisdiction_ocdid = pe.jurisdiction_ocdid
                 WHERE uuid_generate_v5('5364ee76-7dec-41fd-a3b0-7218a73ea92f'::uuid,
                                        pe.id::text || '|' || p.id::text) = c.entity_id
                 LIMIT 1))
       END AS jurisdiction_ocdid
FROM claims c
WHERE c.changeset_id IS NULL AND c.kind <> 'withdraw';

-- A withdraw with no changeset takes its target claim's jurisdiction.
INSERT INTO unattributed (id, created_by, created_at, jurisdiction_ocdid)
SELECT w.id, w.created_by, w.created_at,
       COALESCE(target_changeset.jurisdiction_ocdid, target_unattributed.jurisdiction_ocdid)
FROM claims w
LEFT JOIN claims target ON target.id = w.entity_id
LEFT JOIN changesets target_changeset ON target_changeset.id = target.changeset_id
LEFT JOIN unattributed target_unattributed ON target_unattributed.id = w.entity_id
WHERE w.changeset_id IS NULL AND w.kind = 'withdraw';

CREATE TEMP TABLE attribution ON COMMIT DROP AS
SELECT gen_random_uuid() AS changeset_id, created_by, jurisdiction_ocdid, min(created_at) AS first_at
FROM unattributed
WHERE jurisdiction_ocdid IS NOT NULL
GROUP BY created_by, jurisdiction_ocdid;

INSERT INTO changesets
    (id, kind, jurisdiction_ocdid, created_by_user_id, created_at, updated_at, published_at, comment)
SELECT changeset_id, 'roster_edit', jurisdiction_ocdid, created_by, first_at, first_at, first_at,
       'claims filed before every claim had a changeset (234)'
FROM attribution;

UPDATE claims SET changeset_id = a.changeset_id
FROM unattributed u
JOIN attribution a ON a.jurisdiction_ocdid = u.jurisdiction_ocdid
                  AND a.created_by IS NOT DISTINCT FROM u.created_by
WHERE claims.id = u.id;

COMMIT;
