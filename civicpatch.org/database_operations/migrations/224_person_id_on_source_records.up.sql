-- Who a record is about moves onto the record (plan step 6). It was never rewritten in place, and
-- a re-link is now a `source_record` / `person_id` claim, so the join table has no job left.

BEGIN;

ALTER TABLE source_records ADD COLUMN IF NOT EXISTS person_id uuid;

DO $$
BEGIN
    IF to_regclass('public.source_record_identities') IS NOT NULL THEN
        UPDATE source_records
        SET person_id = source_record_identities.person_id
        FROM source_record_identities
        WHERE source_record_identities.source_record_id = source_records.id
          AND source_records.person_id IS NULL;
    END IF;
    -- A record with no identity was invisible to the fold; NOT NULL must not silently drop it.
    IF EXISTS (SELECT 1 FROM source_records WHERE person_id IS NULL) THEN
        RAISE EXCEPTION 'source_records without an identity: %',
            (SELECT count(*) FROM source_records WHERE person_id IS NULL);
    END IF;
END $$;

ALTER TABLE source_records ALTER COLUMN person_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS source_records_person_id_idx ON source_records (person_id);
DROP TABLE IF EXISTS source_record_identities;

COMMIT;
