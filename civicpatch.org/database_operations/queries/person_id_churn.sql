-- Where does `resolve_people_ids` mint a new id for a person it should have matched? (#2480)
--
-- Reads everyone seen since a jurisdiction last published, and splits those missing from the
-- newest scrape by NAME:
--   same_name_new_id  — the name is on the surviving card or already published, so only the id
--                       changed and the person never went anywhere. Churn.
--   truly_absent      — nobody by that name in either place.
--
-- Prod 2026-08-23: 131 candidates, **123 same_name_new_id (94%)**, across 5 jurisdictions —
-- every one with an apostrophe in its ocdid (l'anse, thompson's_station, sullivan's_island,
-- parker's_crossroads) or an empty place segment (`place:/`). That is the #2480 fingerprint.
--
-- Churn is not cosmetic: it makes every scrape look like a full-roster turnover, which raises
-- NEW_OFFICIAL on everyone and inflates `issue_priority`, so these jurisdictions climb the
-- review queue on the strength of a bug.
--
-- (This began as the transient measurement for the review-window plan. That plan is closed —
-- the transients were almost entirely this.)
--
--   cd ~/cp-infrastructure
--   mise run prod-sql < ~/civicpatch-tools/civicpatch.org/database_operations/queries/person_id_churn.sql
WITH last_publish AS (
    SELECT jurisdiction_ocdid, max(published_at) AS published_at
    FROM requests
    WHERE published_at IS NOT NULL
    GROUP BY jurisdiction_ocdid
),
endpoint AS (
    SELECT DISTINCT ON (jurisdiction_ocdid) jurisdiction_ocdid, id
    FROM requests
    WHERE published_at IS NULL AND dismissed_at IS NULL AND data_json IS NOT NULL
    ORDER BY jurisdiction_ocdid, created_at DESC
),
-- `raw` is one record on the rows the backfill wrote and an array on the ones ingest writes,
-- so the shape is asked rather than assumed.
record_name AS (
    SELECT changeset_id, jurisdiction_ocdid, person_id,
           lower(trim(CASE WHEN jsonb_typeof(raw) = 'array'
                           THEN raw->0->>'name' ELSE raw->>'name' END)) AS name
    FROM source_records
),
observed AS (
    SELECT DISTINCT record_name.jurisdiction_ocdid, record_name.person_id, record_name.name
    FROM record_name
    JOIN requests ON requests.id = record_name.changeset_id
    LEFT JOIN last_publish
           ON last_publish.jurisdiction_ocdid = record_name.jurisdiction_ocdid
    WHERE last_publish.published_at IS NULL
       OR requests.created_at > last_publish.published_at
),
endpoint_people AS (
    SELECT record_name.jurisdiction_ocdid, record_name.person_id, record_name.name
    FROM record_name
    JOIN endpoint ON endpoint.id = record_name.changeset_id
),
transients AS (
    SELECT observed.jurisdiction_ocdid, observed.person_id, observed.name
    FROM observed
    WHERE NOT EXISTS (
        SELECT 1 FROM endpoint_people
        WHERE endpoint_people.jurisdiction_ocdid = observed.jurisdiction_ocdid
          AND endpoint_people.person_id = observed.person_id
    )
    AND NOT EXISTS (
        SELECT 1 FROM people
        WHERE people.id::text = observed.person_id
          AND people.jurisdiction_ocdid = observed.jurisdiction_ocdid
    )
),
-- The same name on the surviving card, or already published under a different id.
named_elsewhere AS (
    SELECT transients.jurisdiction_ocdid, transients.person_id,
           (EXISTS (
                SELECT 1 FROM endpoint_people
                WHERE endpoint_people.jurisdiction_ocdid = transients.jurisdiction_ocdid
                  AND endpoint_people.name = transients.name
            )
            OR EXISTS (
                SELECT 1 FROM people
                WHERE people.jurisdiction_ocdid = transients.jurisdiction_ocdid
                  AND lower(trim(people.data->>'name')) = transients.name
            )) AS same_name
    FROM transients
    WHERE transients.name IS NOT NULL
)
SELECT jurisdiction_ocdid,
       count(*)                                AS transient_people,
       count(*) FILTER (WHERE same_name)       AS same_name_new_id,
       count(*) FILTER (WHERE NOT same_name)   AS truly_absent
FROM named_elsewhere
GROUP BY jurisdiction_ocdid
ORDER BY transient_people DESC;
