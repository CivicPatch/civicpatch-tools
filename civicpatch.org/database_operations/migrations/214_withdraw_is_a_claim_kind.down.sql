BEGIN;

DELETE FROM assertions WHERE kind = 'withdraw';

DELETE FROM changesets
 WHERE kind = 'rollback'
   AND comment = 'migration 214: withdrawals filed before withdraw was a claim kind';

ALTER TABLE changesets DROP COLUMN IF EXISTS comment;

ALTER TABLE assertions DROP CONSTRAINT IF EXISTS assertions_withdraw_names_a_fact;
ALTER TABLE assertions ALTER COLUMN field_path SET NOT NULL;

ALTER TABLE assertions DROP CONSTRAINT IF EXISTS assertions_entity_type_check;
ALTER TABLE assertions ADD CONSTRAINT assertions_entity_type_check
    CHECK (entity_type = ANY (ARRAY[
        'post'::text, 'membership'::text, 'person'::text, 'jurisdiction'::text,
        'organization'::text
    ]));

ALTER TABLE assertions DROP CONSTRAINT IF EXISTS assertions_kind_check;
ALTER TABLE assertions ADD CONSTRAINT assertions_kind_check
    CHECK (kind = ANY (ARRAY['accept'::text, 'reject'::text]));

COMMIT;
