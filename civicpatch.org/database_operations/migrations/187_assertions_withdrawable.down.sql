-- ⚠️ Will fail once a second row exists for any (entity, field) — both indexes below require
-- exactly one. That is true within minutes of real use once this migration is applied, so this
-- file is a correct reversal only against an otherwise-untouched database. Restore from a dump
-- instead of relying on this once the up migration has seen real writes.

BEGIN;

DROP INDEX IF EXISTS assertions_entity_idx;
CREATE INDEX IF NOT EXISTS assertions_entity_idx
    ON assertions (entity_type, entity_id, asserted_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS assertions_one_accept_per_scalar_field
    ON assertions (entity_type, entity_id, field_path)
    WHERE kind = 'accept'
      AND field_path NOT IN ('other_names', 'phones', 'emails', 'urls', 'source_urls', 'post_id');

CREATE UNIQUE INDEX IF NOT EXISTS assertions_one_row_per_value
    ON assertions (entity_type, entity_id, field_path, value)
    WHERE kind = 'reject'
       OR field_path IN ('other_names', 'phones', 'emails', 'urls', 'source_urls', 'post_id');

ALTER TABLE assertions DROP CONSTRAINT IF EXISTS assertions_withdrawn_together;

ALTER TABLE assertions
    DROP COLUMN IF EXISTS withdrawn_reason,
    DROP COLUMN IF EXISTS withdrawn_by,
    DROP COLUMN IF EXISTS withdrawn_at;

COMMIT;
