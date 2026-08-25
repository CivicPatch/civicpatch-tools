BEGIN;

-- Reverses the shape, not the content. `parsed` was a derivation the up migration deliberately
-- stopped storing, so it comes back as `{}` — rolling back is not a data restore.
DO $$
BEGIN
    -- Idempotent: a second run finds the legacy table already back and stops.
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'source_records' AND column_name = 'label') THEN
        RETURN;
    END IF;

    -- Sightings collapse back into one array per person per request. Extracting before the drop
    -- lets the legacy table reclaim its own index and constraint names. `cdn_image` has no
    -- legacy home and is dropped; row ids are new, since the up migration minted per-sighting
    -- ones.
    CREATE TEMP TABLE legacy_people ON COMMIT DROP AS
    SELECT s.request_id,
           i.person_id,
           s.jurisdiction_ocdid,
           jsonb_agg(
               jsonb_build_object(
                   'name', s.name,
                   'label', s.label,
                   'source_url', s.source_url,
                   'url', s.url,
                   'phone', s.phone,
                   'email', s.email,
                   'image', s.image,
                   'start_date', s.start_date,
                   'end_date', s.end_date
               )
               ORDER BY s.created_at, s.label
           ) AS raw,
           min(s.created_at) AS created_at
    FROM source_records s
    JOIN source_record_identities i ON i.source_record_id = s.id
    GROUP BY s.request_id, i.person_id, s.jurisdiction_ocdid;

    DROP TABLE source_record_identities;
    DROP TABLE source_records;

    CREATE TABLE source_records (
        id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        request_id         uuid NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
        person_id          text NOT NULL,
        jurisdiction_ocdid text NOT NULL REFERENCES jurisdictions(jurisdiction_ocdid),
        raw                jsonb NOT NULL,
        parsed             jsonb NOT NULL,
        published_at       timestamptz,
        created_at         timestamptz NOT NULL DEFAULT now()
    );

    CREATE INDEX source_records_jurisdiction_ocdid_idx ON source_records (jurisdiction_ocdid);
    CREATE INDEX source_records_request_id_idx ON source_records (request_id);
    CREATE INDEX source_records_person_id_created_at_idx
        ON source_records (person_id, created_at DESC);
    CREATE INDEX source_records_parsed_idx ON source_records USING gin (parsed jsonb_path_ops);

    INSERT INTO source_records
        (request_id, person_id, jurisdiction_ocdid, raw, parsed, created_at)
    SELECT request_id, person_id, jurisdiction_ocdid, raw, '{}'::jsonb, created_at
    FROM legacy_people;
END $$;

COMMIT;
