-- `change_logs.changes` collapses onto one shape, and `EntityType` grows to name every entity
-- that shape can be about.
--
-- Four payload models described the same event — an entity, its name at the time, and the
-- fields that moved — with different key names each:
--
--   person       {person_id, person_name, fields}
--   post         {post_id, role_id, division_ocdid, label, fields}
--   membership   {membership_id, person_id, person_name, post_id, role_id, label, fields}
--   jurisdiction {jurisdiction_ocdid, jurisdiction_name, fields}
--
--                     ↓
--   {entity_type, entity_id, subject, detail, fields}
--
-- `detail` is a second name, and only a membership has one: an assignment is read as a person
-- *and* the seat they took. Everything else is fully described by its subject plus the fields
-- that moved, so it stays null.
--
-- `subject` is the name as it read *at the time*, which is the one thing here that cannot be
-- recovered by joining: the entity may since have been renamed, or deleted outright — and a log
-- saying "deleted d6fe691e-…" is unreadable.
--
-- **The CHECK widens first, because the shape needs it.** `EntityType` was
-- `post | membership | person`, which was enough while only assertions used it. Two of the four
-- payloads above are about a jurisdiction, and an organization will follow — creating or
-- renaming one is currently invisible, having no change log type at all. One vocabulary rather
-- than two: an assertion and a change are both "somebody said something about this entity",
-- and they should not disagree about what an entity is. Widening a CHECK admits no existing row
-- that was not already legal, so nothing is backfilled.
--
-- **What is dropped, and why it is not a loss.** `role_id`, `division_ocdid`, `post_id` and
-- `person_id` on the post and membership shapes are joinable context, and the change itself is
-- already in `fields` (`post_id` before/after for a move, `label` for a rename). `reason` on a
-- dismissal duplicates `changesets.dismissed_reason`, which the code already calls the state to
-- read — so those payloads become NULL rather than being reshaped into a field change they
-- never were.
--
-- **Role taxonomy keeps its own shape**, deliberately: 14 rows across `delete_role`,
-- `reorder_roles`, `add_role` and `exclude_role`, all `{kind, role}`. A role is global — it
-- names no jurisdiction and belongs to no entity — which is why it is already excluded from
-- both the jurisdiction history and the sync feed. So this is "one shape for entity changes",
-- not one shape for every log.
--
-- `assert_field` is not handled: it has **zero rows**. Every one of the 990 assertions was
-- written by `_accept_fields` / `_accept_published` inside a publish, which record no log at
-- all. Its `sources` field — "phoned the clerk" — has therefore never been written either.

BEGIN;

ALTER TABLE assertions DROP CONSTRAINT IF EXISTS assertions_entity_type_check;
ALTER TABLE assertions ADD CONSTRAINT assertions_entity_type_check
    CHECK (entity_type IN ('post', 'membership', 'person', 'jurisdiction', 'organization'));

-- person: add_person | edit_person | delete_person
UPDATE change_logs
   SET changes = jsonb_build_object(
           'entity_type', 'person',
           'entity_id',   changes->>'person_id',
           'subject',     changes->>'person_name',
           'fields',      COALESCE(changes->'fields', '[]'::jsonb))
 WHERE changes ? 'person_id' AND NOT changes ? 'membership_id';

-- membership: assign_membership. `person_name` is the subject — a seat is read as the person
-- holding it, and `membership_id` is what the row is about.
UPDATE change_logs
   SET changes = jsonb_build_object(
           'entity_type', 'membership',
           'entity_id',   changes->>'membership_id',
           'subject',     changes->>'person_name',
           'detail',      COALESCE(changes->>'label', changes->>'role_id'),
           'fields',      COALESCE(changes->'fields', '[]'::jsonb))
 WHERE changes ? 'membership_id';

-- post: add_post | edit_post | delete_post. `label` is the seat's own name; `role_id` stands in
-- where a post was never labelled.
UPDATE change_logs
   SET changes = jsonb_build_object(
           'entity_type', 'post',
           'entity_id',   changes->>'post_id',
           'subject',     COALESCE(changes->>'label', changes->>'role_id'),
           'fields',      COALESCE(changes->'fields', '[]'::jsonb))
 WHERE changes ? 'post_id' AND NOT changes ? 'membership_id';

-- jurisdiction: edit_jurisdiction
UPDATE change_logs
   SET changes = jsonb_build_object(
           'entity_type', 'jurisdiction',
           'entity_id',   changes->>'jurisdiction_ocdid',
           'subject',     changes->>'jurisdiction_name',
           'fields',      COALESCE(changes->'fields', '[]'::jsonb))
 WHERE changes ? 'jurisdiction_ocdid';

-- dismissals: the reason lives on `changesets.dismissed_reason`, so the payload has nothing
-- left to say.
UPDATE change_logs SET changes = NULL WHERE changes ? 'reason';

COMMIT;
