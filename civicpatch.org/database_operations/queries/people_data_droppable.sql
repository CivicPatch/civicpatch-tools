-- Is `people.data` safe to drop? One row, every gate in it.
--
-- ONE STATEMENT ON PURPOSE. `prod-sql` runs `cur = conn.execute(sql)` and prints a single
-- result set, so a file with several statements executes them all and reports only the first.
-- An earlier version of this file had three and silently answered one third of the question.
--
--   cd ~/cp-infrastructure
--   mise run prod-sql < ~/civicpatch-tools/civicpatch.org/database_operations/queries/people_data_droppable.sql
--
-- PASS: `mismatched` = 0 AND `office_differs` = 0.
-- `office_would_go_null` is not a gate — it is the number you are accepting. Those people have
-- no membership at all, so their office lives only in the blob and the migration destroys it.
-- List them with `people_without_memberships.sql` before deciding.
--
-- dev: 20712 | 0 | 20643 | 44 | 25 | 0        prod 2026-08-24: 23086 | 0 | ? | ? | ? | ?
WITH rebuilt AS (
    SELECT
        people.id,
        -- Must stay a copy of `PERSON_JSON` in database/people.py, minus the three keys below.
        -- No `jsonb_strip_nulls`: `PERSON_JSON` has none, and adding it here reported 18,540
        -- false mismatches on dev by dropping the null-valued keys `data` actually carries.
        (people.data - 'office' - 'memberships' - 'labels') AS stored,
        jsonb_build_object(
            'id', people.id::text,
            'name', people.name,
            'other_names', to_jsonb(people.other_names),
            'phones', to_jsonb(people.phones),
            'emails', to_jsonb(people.emails),
            'urls', to_jsonb(people.urls),
            'source_urls', to_jsonb(people.source_urls),
            'image', people.image,
            'cdn_image', people.cdn_image,
            'start_date', people.start_date,
            'end_date', people.end_date,
            'jurisdiction_ocdid', people.jurisdiction_ocdid,
            'updated_at', to_char(people.updated_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') || '+00:00'
        ) AS from_columns,
        people.data->'office' AS office_from_blob,
        EXISTS (SELECT 1 FROM memberships m
                WHERE m.person_id = people.id AND m.closed_at IS NULL) AS has_open,
        EXISTS (SELECT 1 FROM memberships m WHERE m.person_id = people.id) AS has_any,
        -- The fallback `PERSON_OFFICE` uses now: still-open first, then most recent.
        (SELECT jsonb_build_object(
                    'name', array_to_string(m.source_labels, ' - '),
                    'division_ocdid', p.division_ocdid)
         FROM memberships m JOIN posts p ON p.id = m.post_id
         WHERE m.person_id = people.id
         ORDER BY (m.closed_at IS NULL) DESC, m.first_seen_at DESC
         LIMIT 1) AS office_from_membership
    FROM people
)
SELECT
    count(*)                                                    AS people_total,
    -- The veto. A field 134 split out has drifted from the blob, and dropping it loses that.
    count(*) FILTER (WHERE from_columns <> stored)              AS mismatched,
    count(*) FILTER (WHERE has_open)                            AS has_open_membership,
    count(*) FILTER (WHERE NOT has_open AND has_any)            AS closed_only,
    count(*) FILTER (WHERE NOT has_any)                         AS office_would_go_null,
    -- The second veto: whether the closed-membership fallback reproduces what the blob said,
    -- or merely approximates it. Above 0 means read those rows before going further.
    count(*) FILTER (WHERE NOT has_open AND has_any
                       AND office_from_membership IS DISTINCT FROM office_from_blob)
                                                                AS office_differs
FROM rebuilt;
