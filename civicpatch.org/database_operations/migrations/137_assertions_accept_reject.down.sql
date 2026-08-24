BEGIN;

DROP INDEX assertions_one_row_per_value;
DROP INDEX assertions_one_accept_per_scalar_field;

ALTER TABLE assertions ADD CONSTRAINT assertions_no_exact_duplicate
    UNIQUE NULLS NOT DISTINCT (entity_type, entity_id, field_path, asserted_by, asserted_at);

ALTER TABLE assertions ADD CONSTRAINT assertions_correct_has_value
    CHECK (kind <> 'correct' OR value IS NOT NULL OR field_path IS NOT NULL);

ALTER TABLE assertions ALTER COLUMN value DROP NOT NULL;
ALTER TABLE assertions ALTER COLUMN field_path DROP NOT NULL;

ALTER TABLE assertions DROP CONSTRAINT assertions_kind_check;
ALTER TABLE assertions ADD CONSTRAINT assertions_kind_check
    CHECK (kind = ANY (ARRAY['confirm'::text, 'correct'::text, 'retract'::text]));

COMMIT;
