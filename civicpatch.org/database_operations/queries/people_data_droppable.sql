-- Is `people.data` safe to drop on prod? Three reads, in the order they can veto the migration.
--
-- Everything below was measured on dev and came back clean. Dev is seeded and 20k rows; prod
-- has different vintages of person, which is the whole reason to re-measure rather than assume.
--
--   cd ~/cp-infrastructure
--   mise run prod-sql < ~/civicpatch-tools/civicpatch.org/database_operations/queries/people_data_droppable.sql

-- 1. Does the shape assembled from columns still equal the blob?
--
-- The veto. If `mismatched` is not 0, some field 134 split out has drifted from `data` on prod
-- and dropping the column loses the difference. Dev: 0 across all 20,712 rows.
--
-- `office`, `memberships` and `labels` are subtracted from both sides: they are views over
-- memberships, deliberately not columns, and no column could reproduce them. Row 2 covers
-- `office` on its own terms.
--
-- The build below must stay a copy of `PERSON_JSON` in database/people.py minus those three
-- keys. No `jsonb_strip_nulls` — `PERSON_JSON` has none, and adding it here reported 18,540
-- false mismatches on dev by dropping the null-valued keys `data` actually carries.
SELECT
    count(*)                                                   AS people_total,
    count(*) FILTER (WHERE rebuilt <> stored)                  AS mismatched
FROM (
    SELECT
        (people.data - 'office' - 'memberships' - 'labels')    AS stored,
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
        )                                                      AS rebuilt
    FROM people
) comparison;

-- 2. Who loses an office, and does the fallback reproduce the blob for the rest?
--
-- `PERSON_OFFICE` reads the last closed membership now. For a person with no membership at
-- all there is nothing to fall back to and their office goes null — that text lives only in
-- `data`, so the migration destroys it rather than just hiding it.
--
-- Dev: 20,643 open / 44 closed-only / 25 none-at-all, and `differs` was 0 — every closed-only
-- person's membership reproduced `data->'office'` exactly. `differs` above 0 on prod means the
-- fallback is an approximation there, not a reproduction, and is worth reading row by row.
WITH resolved AS (
    SELECT
        people.id,
        people.jurisdiction_ocdid,
        people.data->'office'                                  AS from_blob,
        EXISTS (SELECT 1 FROM memberships m
                WHERE m.person_id = people.id AND m.closed_at IS NULL)
                                                               AS has_open,
        EXISTS (SELECT 1 FROM memberships m WHERE m.person_id = people.id)
                                                               AS has_any,
        (SELECT jsonb_build_object(
                    'name', array_to_string(m.source_labels, ' - '),
                    'division_ocdid', p.division_ocdid)
         FROM memberships m JOIN posts p ON p.id = m.post_id
         WHERE m.person_id = people.id
         ORDER BY (m.closed_at IS NULL) DESC, m.first_seen_at DESC
         LIMIT 1)                                              AS from_membership
    FROM people
)
SELECT
    count(*) FILTER (WHERE has_open)                           AS has_open_membership,
    count(*) FILTER (WHERE NOT has_open AND has_any)           AS closed_only,
    count(*) FILTER (WHERE NOT has_any)                        AS office_would_go_null,
    count(*) FILTER (WHERE NOT has_open AND has_any
                       AND from_membership IS DISTINCT FROM from_blob)
                                                               AS differs
FROM resolved;

-- 3. What exactly would be lost, so the number in row 2 can be judged rather than accepted.
--
-- A handful of stale seed rows is a shrug. A live councilmember is a backfill: mint their post
-- and a closed membership before the migration, not after.
SELECT
    people.jurisdiction_ocdid,
    people.data->'office'->>'name'                             AS office_name,
    people.status,
    people.updated_at::date                                    AS last_touched
FROM people
WHERE NOT EXISTS (SELECT 1 FROM memberships m WHERE m.person_id = people.id)
ORDER BY people.updated_at DESC
LIMIT 50;
