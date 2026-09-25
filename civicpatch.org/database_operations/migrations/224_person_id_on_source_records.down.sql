-- Exactly reverses 224.

BEGIN;

CREATE TABLE IF NOT EXISTS source_record_identities (
    source_record_id uuid PRIMARY KEY REFERENCES source_records (id) ON DELETE CASCADE,
    person_id uuid NOT NULL,
    resolved_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS source_record_identities_person_id_idx
    ON source_record_identities (person_id);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'source_records' AND column_name = 'person_id'
    ) THEN
        INSERT INTO source_record_identities (source_record_id, person_id)
        SELECT id, person_id FROM source_records
        ON CONFLICT (source_record_id) DO NOTHING;
    END IF;
END $$;

DROP INDEX IF EXISTS source_records_person_id_idx;
ALTER TABLE source_records DROP COLUMN IF EXISTS person_id;

COMMIT;
