-- `post_id` becomes a list-valued assertion field.
--
-- A reviewer picks one post, so a scalar assertion looks right — but the uniqueness would be
-- per `(person, field_path)`, and a person can hold one open membership per *organization*.
-- With a second body in a jurisdiction, picking their school-board post would overwrite their
-- council post on the same key: silently, and looking like it saved.
--
-- A post names its own organization (`posts.organization_id`, NOT NULL), so a list of accepted
-- posts is self-scoping — at most one per body, enforced downstream by
-- `memberships_one_open_per_organization` rather than here.
--
-- Both indexes from 137 hardcode the list-field array, and `core/people_edits.LIST_FIELDS`
-- mirrors it. They have to move together: adding `post_id` on the Python side alone raises
-- `duplicate key value violates unique constraint "assertions_one_accept_per_scalar_field"`
-- the second time anyone picks a post for the same person.
--
-- Indexes are recreated rather than altered: postgres cannot change a partial index's
-- predicate in place.
BEGIN;

DROP INDEX IF EXISTS assertions_one_accept_per_scalar_field;
CREATE UNIQUE INDEX IF NOT EXISTS assertions_one_accept_per_scalar_field
    ON assertions (entity_type, entity_id, field_path)
    WHERE kind = 'accept'
      AND field_path <> ALL (ARRAY[
          'other_names', 'phones', 'emails', 'urls', 'source_urls', 'post_id'
      ]);

DROP INDEX IF EXISTS assertions_one_row_per_value;
CREATE UNIQUE INDEX IF NOT EXISTS assertions_one_row_per_value
    ON assertions (entity_type, entity_id, field_path, value)
    WHERE kind = 'reject'
       OR field_path = ANY (ARRAY[
          'other_names', 'phones', 'emails', 'urls', 'source_urls', 'post_id'
      ]);

COMMIT;
