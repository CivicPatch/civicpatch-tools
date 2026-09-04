-- Deliberately irreversible in part, and it says so rather than pretending.
--
-- The up drops `role_id`, `division_ocdid`, and the second and third ids on a membership. Those
-- are joinable from the entity, but this migration does not have them to hand — reconstructing
-- would mean querying `posts` and `memberships` for rows that may since have been deleted, and
-- inventing values for the ones that have.
--
-- What it does restore is the shape, so the old readers parse: the keys they required come back
-- from `entity_type`, and the context keys they tolerated come back empty. A dismissal's
-- `reason` is read from `changesets` rather than guessed.
--
-- The CHECK narrows last, after the payloads no longer name a jurisdiction. It fails if any
-- assertion uses the two new values, rather than deleting or remapping somebody's assertion.

BEGIN;

UPDATE change_logs
   SET changes = jsonb_build_object(
           'person_id',   changes->>'entity_id',
           'person_name', changes->>'subject',
           'fields',      changes->'fields')
 WHERE changes->>'entity_type' = 'person';

UPDATE change_logs
   SET changes = jsonb_build_object(
           'membership_id', changes->>'entity_id',
           'person_id',     '',
           'person_name',   changes->>'subject',
           'post_id',       '',
           'role_id',       '',
           'label',         changes->>'detail',
           'fields',        changes->'fields')
 WHERE changes->>'entity_type' = 'membership';

UPDATE change_logs
   SET changes = jsonb_build_object(
           'post_id',        changes->>'entity_id',
           'role_id',        '',
           'division_ocdid', '',
           'label',          changes->>'subject',
           'fields',         changes->'fields')
 WHERE changes->>'entity_type' = 'post';

UPDATE change_logs
   SET changes = jsonb_build_object(
           'jurisdiction_ocdid',   changes->>'entity_id',
           'jurisdiction_name',    changes->>'subject',
           'fields',               changes->'fields')
 WHERE changes->>'entity_type' = 'jurisdiction';

UPDATE change_logs cl
   SET changes = jsonb_build_object('reason', r.dismissed_reason)
  FROM changesets r
 WHERE cl.type = 'dismiss_review'
   AND cl.changeset_id = r.id::text
   AND r.dismissed_reason IS NOT NULL;

ALTER TABLE assertions DROP CONSTRAINT IF EXISTS assertions_entity_type_check;
ALTER TABLE assertions ADD CONSTRAINT assertions_entity_type_check
    CHECK (entity_type IN ('post', 'membership', 'person'));

COMMIT;
