BEGIN;

-- Popolo `sources` on a membership: each label a source gave, with the page it came from. Replaces
-- `source_labels`, which kept the labels and lost the pages.
ALTER TABLE memberships ADD COLUMN IF NOT EXISTS sources jsonb NOT NULL DEFAULT '[]'::jsonb;

-- The distinct notes in first-seen order: what `source_labels` held, for every reader still named so.
CREATE OR REPLACE FUNCTION membership_source_labels(sources jsonb) RETURNS text[]
LANGUAGE sql IMMUTABLE AS $$
    SELECT COALESCE(array_agg(note ORDER BY first_position), '{}')
    FROM (
        SELECT source->>'note' AS note, min(position) AS first_position
        FROM jsonb_array_elements(sources) WITH ORDINALITY AS entry(source, position)
        GROUP BY source->>'note'
    ) notes
$$;

-- Guarded so a re-run after the drop is a no-op. Each label's url is the latest source record
-- resolved to this person with that label in this organization; null where none matches.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'memberships' AND column_name = 'source_labels'
    ) THEN
        UPDATE memberships SET sources = COALESCE((
            SELECT jsonb_agg(
                jsonb_build_object(
                    'url', (
                        SELECT source_records.source_url
                        FROM source_records
                        JOIN source_record_identities
                          ON source_record_identities.source_record_id = source_records.id
                        WHERE source_record_identities.person_id = memberships.person_id
                          AND source_records.organization_id = memberships.organization_id
                          AND source_records.label = labels.label
                        ORDER BY source_records.created_at DESC
                        LIMIT 1
                    ),
                    'note', labels.label
                )
                ORDER BY labels.position
            )
            FROM unnest(memberships.source_labels) WITH ORDINALITY AS labels(label, position)
        ), '[]'::jsonb);

        ALTER TABLE memberships DROP COLUMN IF EXISTS source_labels;
    END IF;
END
$$;

COMMIT;
