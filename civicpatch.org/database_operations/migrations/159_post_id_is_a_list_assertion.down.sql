-- Exact reverse of 159: the two indexes as 137 defined them, without `post_id`.
--
-- Any accepted `post_id` rows beyond one per person will block this, which is correct — the
-- rollback would otherwise silently discard a reviewer's picks.
BEGIN;

DROP INDEX IF EXISTS assertions_one_accept_per_scalar_field;
CREATE UNIQUE INDEX IF NOT EXISTS assertions_one_accept_per_scalar_field
    ON assertions (entity_type, entity_id, field_path)
    WHERE kind = 'accept'
      AND field_path <> ALL (ARRAY[
          'other_names', 'phones', 'emails', 'urls', 'source_urls'
      ]);

DROP INDEX IF EXISTS assertions_one_row_per_value;
CREATE UNIQUE INDEX IF NOT EXISTS assertions_one_row_per_value
    ON assertions (entity_type, entity_id, field_path, value)
    WHERE kind = 'reject'
       OR field_path = ANY (ARRAY[
          'other_names', 'phones', 'emails', 'urls', 'source_urls'
      ]);

COMMIT;
