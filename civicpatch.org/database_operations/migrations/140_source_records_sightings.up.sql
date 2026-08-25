BEGIN;

-- `source_records` becomes one row per sighting, and stores nothing derived.
--
-- Plan: .scratch/2026-08-24-source-records-shape.md
--
-- It held two grains: `raw` was an array of sightings, `parsed` was one person's reconciliation
-- across them — and `parts` inside `parsed` was per-label data buried in a person-grain blob.
--
-- `parsed` goes entirely. It is `parse_record(labels, taxonomy)`, which is pure, so storing it
-- only means storing an answer that goes stale: every row's `parsed` was left wrong by the
-- label-segmentation fix earlier today, and nothing would ever refresh it. It is recomputed on
-- read now, which is the property records exist for.
DO $$
BEGIN
    -- Idempotent: a second run finds the reshaped table and stops.
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                   WHERE table_name = 'source_records' AND column_name = 'raw') THEN
        RETURN;
    END IF;

    -- Prod is empty, so this moves nothing there. Dev holds real sightings worth keeping, and
    -- expanding them before the drop lets the new table own the old index and constraint names.
    -- Object-shaped rows are skipped: they predate the records flip and hold a single merged
    -- person rather than sightings, so there is nothing to expand.
    CREATE TEMP TABLE legacy_sightings ON COMMIT DROP AS
    SELECT gen_random_uuid() AS id,
           s.request_id,
           s.jurisdiction_ocdid,
           s.person_id,
           s.created_at,
           record
    FROM source_records s,
         LATERAL jsonb_array_elements(s.raw) AS record
    WHERE jsonb_typeof(s.raw) = 'array'
      AND record->>'name' IS NOT NULL
      AND record->>'label' IS NOT NULL
      AND record->>'source_url' IS NOT NULL;

    DROP TABLE source_records;

    -- A row is a sighting: what one page said about one person, once. `PersonRecord` is nine
    -- scalars, so there is no jsonb here at all.
    CREATE TABLE source_records (
        id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        request_id         uuid NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
        jurisdiction_ocdid text NOT NULL REFERENCES jurisdictions(jurisdiction_ocdid),
        name               text NOT NULL,
        -- One record per label is the contract with the pipeline: a person seen under two
        -- titles is two rows, so nothing has to un-join them later.
        label              text NOT NULL,
        source_url         text NOT NULL,
        url                text,
        phone              text,
        email              text,
        -- Named as on `people`: where the photo came from, and where we put it. Both stored
        -- rather than composed — the R2 key is a fact about a file, not a template. The
        -- pipeline's `local://{hash}` ref is not kept; it means nothing once the zip is gone.
        image              text,
        cdn_image          text,
        -- Text, not date: sources give partial dates ("2024", "2024-01") and Popolo allows them.
        start_date         text,
        end_date           text,
        created_at         timestamptz NOT NULL DEFAULT now()
    );

    CREATE INDEX source_records_label_idx ON source_records (label);
    CREATE INDEX source_records_jurisdiction_ocdid_idx ON source_records (jurisdiction_ocdid);
    CREATE INDEX source_records_request_id_idx ON source_records (request_id);

    -- Which sightings are the same human — kept out of the evidence deliberately.
    --
    -- Linkage is not a fact about a page, and it is not stable across runs (#2480). With
    -- `person_id` on the sighting, every re-resolution would be an UPDATE over evidence, which
    -- is what this shape exists to prevent. Re-linking rewrites this table instead, and the
    -- records are never touched.
    CREATE TABLE source_record_identities (
        source_record_id uuid PRIMARY KEY REFERENCES source_records(id) ON DELETE CASCADE,
        person_id        text NOT NULL,
        resolved_at      timestamptz NOT NULL DEFAULT now()
    );

    CREATE INDEX source_record_identities_person_id_idx ON source_record_identities (person_id);

    INSERT INTO source_records
        (id, request_id, jurisdiction_ocdid, name, label, source_url,
         url, phone, email, image, cdn_image, start_date, end_date, created_at)
    SELECT id, request_id, jurisdiction_ocdid,
           record->>'name', record->>'label', record->>'source_url',
           record->>'url', record->>'phone', record->>'email',
           -- Legacy rows carry only the `local://` ref, so neither url survives the move.
           NULL, NULL,
           record->>'start_date', record->>'end_date', created_at
    FROM legacy_sightings;

    INSERT INTO source_record_identities (source_record_id, person_id)
    SELECT id, person_id FROM legacy_sightings;
END $$;

COMMIT;
