-- What stands between us and retiring `requests.data_json`.
--
-- ONE STATEMENT: `prod-sql` prints a single result set, so several would run and report only
-- the first.
--
--   cd ~/cp-infrastructure
--   mise run prod-sql < ~/civicpatch-tools/civicpatch.org/database_operations/queries/data_json_retirement.sql
--
-- prod after the 2026-08-24 cleanup: 4341 | 0 | 4341 | 0 | 0 | 0 | 23066 | 170 | 2
--
-- `source_records` is empty. Every row it held was a reconstruction of `data_json` with an
-- invented label/url pairing, and no scrape has run since the records flip — so there is
-- nothing to replay reconciliation over until one does. That is what this query now tracks:
-- `requests_with_records` climbing off 0 is the signal that the records path is alive.
--
-- `roster_only` = 4341 is therefore every request, not a gap to backfill.
--
-- `old_person_shape` must stay 0: `insert_source_records` takes a list per person, so the
-- writer cannot produce the old single-object shape. A non-zero reading means someone wrote
-- around it.
--
-- The last three size the prize rather than the work: `unparsed_residue` is what a future
-- parser improvement could reach if reconciliation were replayed, and `slash_labels` is what
-- the segmentation fix alone would correct.
SELECT
    (SELECT count(*) FROM requests WHERE data_json IS NOT NULL)          AS requests_with_roster,
    (SELECT count(DISTINCT request_id) FROM source_records)              AS requests_with_records,
    (SELECT count(*) FROM requests r
      WHERE r.data_json IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM source_records s
                        WHERE s.request_id = r.id))                      AS roster_only,
    (SELECT count(*) FROM source_records
      WHERE jsonb_typeof(raw) = 'array')                                 AS sighting_shape,
    (SELECT count(*) FROM source_records
      WHERE jsonb_typeof(raw) = 'object')                                AS old_person_shape,
    (SELECT count(*) FROM source_records
      WHERE raw @> '[{"_reconstructed_from": "requests.data_json"}]')     AS reconstructed_from_data_json,
    (SELECT count(*) FROM memberships)                                   AS memberships_total,
    (SELECT count(*) FROM memberships
      WHERE unmatched_text <> '{}')                                      AS unparsed_residue,
    (SELECT count(*) FROM memberships m
      WHERE EXISTS (SELECT 1 FROM unnest(m.source_labels) l
                    WHERE l LIKE '%/%'))                                 AS slash_labels;
