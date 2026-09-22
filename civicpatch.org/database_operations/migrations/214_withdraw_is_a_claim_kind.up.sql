BEGIN;

-- A withdrawal becomes a fact of its own: a `withdraw` row naming the fact it cancels, under
-- the changeset that cancelled it. That is what lets a rollback be rolled back, and what lets
-- records and page rows be withdrawn the same way claims are. The `withdrawn_*` columns stay,
-- written alongside and read by nothing new, until the rename migration drops them.

ALTER TABLE assertions DROP CONSTRAINT IF EXISTS assertions_kind_check;
ALTER TABLE assertions ADD CONSTRAINT assertions_kind_check
    CHECK (kind = ANY (ARRAY['accept'::text, 'reject'::text, 'withdraw'::text]));

ALTER TABLE assertions DROP CONSTRAINT IF EXISTS assertions_entity_type_check;
ALTER TABLE assertions ADD CONSTRAINT assertions_entity_type_check
    CHECK (entity_type = ANY (ARRAY[
        'post'::text, 'membership'::text, 'person'::text, 'jurisdiction'::text,
        'organization'::text, 'source_record'::text, 'source_page'::text, 'claim'::text
    ]));

-- A withdraw names a whole fact, not a field of one.
ALTER TABLE assertions ALTER COLUMN field_path DROP NOT NULL;
ALTER TABLE assertions DROP CONSTRAINT IF EXISTS assertions_withdraw_names_a_fact;
ALTER TABLE assertions ADD CONSTRAINT assertions_withdraw_names_a_fact
    CHECK ((kind = 'withdraw') = (field_path IS NULL));

-- Required by the rollback route; a rollback with no reason is not one an admin should file.
ALTER TABLE changesets ADD COLUMN IF NOT EXISTS comment text;

-- A withdrawal filed with no rollback changeset behind it (clearing a label back to derived,
-- for instance) gets one, per user and jurisdiction, dated at their earliest such withdrawal.
-- The id is derived from those two so a rerun finds the row it already made.
INSERT INTO changesets
    (id, kind, jurisdiction_ocdid, created_by_user_id, resolved_by_user_id,
     created_at, published_at, comment)
SELECT md5('214:' || a.withdrawn_by::text || ':' || coalesce(j.jurisdiction_ocdid, ''))::uuid,
       'rollback', j.jurisdiction_ocdid, a.withdrawn_by, a.withdrawn_by,
       min(a.withdrawn_at), min(a.withdrawn_at),
       'migration 214: withdrawals filed before withdraw was a claim kind'
FROM assertions a
LEFT JOIN LATERAL (
    SELECT CASE a.entity_type
        WHEN 'person' THEN (SELECT jurisdiction_ocdid FROM people WHERE id = a.entity_id)
        WHEN 'post' THEN (SELECT jurisdiction_ocdid FROM posts WHERE id = a.entity_id)
        WHEN 'membership' THEN (
            SELECT p.jurisdiction_ocdid FROM memberships m
            JOIN posts p ON p.id = m.post_id WHERE m.id = a.entity_id)
        WHEN 'organization' THEN (SELECT jurisdiction_ocdid FROM organizations WHERE id = a.entity_id)
    END AS jurisdiction_ocdid
) j ON true
WHERE a.withdrawn_at IS NOT NULL AND a.withdrawn_by_changeset_id IS NULL
GROUP BY a.withdrawn_by, j.jurisdiction_ocdid
ON CONFLICT (id) DO NOTHING;

-- One withdraw row per withdrawn assertion, under its rollback changeset or the one above.
INSERT INTO assertions
    (entity_type, entity_id, field_path, kind, value, created_by, created_at, changeset_id)
SELECT 'claim', a.id, NULL, 'withdraw', 'null'::jsonb, a.withdrawn_by, a.withdrawn_at,
       coalesce(
           a.withdrawn_by_changeset_id,
           md5('214:' || a.withdrawn_by::text || ':' || coalesce(j.jurisdiction_ocdid, ''))::uuid
       )
FROM assertions a
LEFT JOIN LATERAL (
    SELECT CASE a.entity_type
        WHEN 'person' THEN (SELECT jurisdiction_ocdid FROM people WHERE id = a.entity_id)
        WHEN 'post' THEN (SELECT jurisdiction_ocdid FROM posts WHERE id = a.entity_id)
        WHEN 'membership' THEN (
            SELECT p.jurisdiction_ocdid FROM memberships m
            JOIN posts p ON p.id = m.post_id WHERE m.id = a.entity_id)
        WHEN 'organization' THEN (SELECT jurisdiction_ocdid FROM organizations WHERE id = a.entity_id)
    END AS jurisdiction_ocdid
) j ON true
WHERE a.withdrawn_at IS NOT NULL
  AND a.kind <> 'withdraw'
  AND NOT EXISTS (
      SELECT 1 FROM assertions w WHERE w.kind = 'withdraw' AND w.entity_id = a.id
  );

COMMIT;
