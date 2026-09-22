BEGIN;

-- Most live people in production (21,246 on 2026-09-21) arrived before `source_records` existed,
-- so nothing the fold reads names them. This gives each the records a page would have left,
-- so the fold derives the rosters the projection already shows.
--
-- A temporary function, gone when the migration's connection closes: nothing is left in the
-- database. Idempotent by construction (it only picks up live people with no published
-- record), so the dev seed, which reloads `people` and `memberships` after migrations have
-- run, simply executes this file again.
--
-- Rules, each for a reason:
--   * One `sheet_import` changeset per jurisdiction, dated a second before the earliest
--     `first_seen_at` it carries, all three timestamps alike: every changeset has an `updated_at`
--     (`assign` dates a membership by it), and at that date every real scrape since is newer,
--     for freshness and for the superseded check alike.
--   * Every open membership in an organization that holds at least one such person, not only
--     theirs: the changeset is a read of that organization, and a read that listed only some of
--     its people would retire the rest.
--   * Values from `people`, minus any a live accept claim put there, so rolling that claim back
--     still reverts it. `name` is NOT NULL on a record, so a claimed name is carried anyway.
--   * One record per open membership carrying each list's first value; one more record per
--     further value, on the person's first membership, as a page lists two lines; a further
--     `source_url` is a further page, so it gets a record the same way. `created_at`
--     steps by a microsecond so the fold keeps each list in the order `people` holds it.
--   * The label is the membership's stored note, which is what the page said, else the role's.
--   * Closed memberships are skipped: a record would reopen them. Their history is step 15's.
CREATE OR REPLACE FUNCTION pg_temp.backfill_source_records() RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    inserted integer;
BEGIN
    DROP TABLE IF EXISTS backfill_roster;
    CREATE TEMP TABLE IF NOT EXISTS backfill_roster ON COMMIT DROP AS
    -- A record under an unpublished changeset (pending review, dismissed) counts for nothing in
    -- the fold, so a person whose only records are there needs one too.
    WITH record_less AS (
        SELECT DISTINCT m.organization_id
        FROM memberships m
        WHERE m.closed_at IS NULL
          AND NOT EXISTS (
              SELECT 1
              FROM source_record_identities i
              JOIN source_records s ON s.id = i.source_record_id
              JOIN changesets c ON c.id = s.changeset_id
              WHERE i.person_id = m.person_id AND c.published_at IS NOT NULL
          )
    )
    SELECT m.id AS membership_id, m.person_id, m.organization_id, m.first_seen_at,
           m.start_date, m.end_date,
           p.jurisdiction_ocdid,
           coalesce(nullif(m.sources -> 0 ->> 'note', ''), r.label, p.role_id) AS label,
           person.name, person.other_names, person.phones, person.emails, person.urls,
           person.image, person.cdn_image, person.source_urls,
           coalesce(person.source_urls[1], j.data ->> 'url', '') AS source_url,
           row_number() OVER (PARTITION BY m.person_id ORDER BY m.id) = 1 AS carries_extras
    FROM memberships m
    JOIN record_less USING (organization_id)
    JOIN posts p ON p.id = m.post_id
    JOIN people person ON person.id = m.person_id
    LEFT JOIN roles r ON r.id = p.role_id
    LEFT JOIN jurisdictions j ON j.jurisdiction_ocdid = p.jurisdiction_ocdid
    WHERE m.closed_at IS NULL;

    INSERT INTO changesets
        (id, kind, jurisdiction_ocdid, created_by_user_id, resolved_by_user_id,
         created_at, published_at, updated_at, comment)
    SELECT md5('215:' || jurisdiction_ocdid)::uuid, 'sheet_import', jurisdiction_ocdid,
           -- The system user (160), as for an auto-publish: nobody did this by hand.
           '00000000-0000-4000-8000-000000000001', '00000000-0000-4000-8000-000000000001',
           min(first_seen_at) - interval '1 second', min(first_seen_at) - interval '1 second',
           min(first_seen_at) - interval '1 second',
           'migration 215: roster loaded before source records existed'
    FROM backfill_roster
    GROUP BY jurisdiction_ocdid
    ON CONFLICT (id) DO NOTHING;

    -- The values a record may carry: `people`'s own, in order, minus any a live accept put there.
    DROP TABLE IF EXISTS backfill_values;
    CREATE TEMP TABLE IF NOT EXISTS backfill_values ON COMMIT DROP AS
    SELECT b.membership_id, b.person_id, field, value,
           row_number() OVER (PARTITION BY b.membership_id, field ORDER BY position) AS slot
    FROM backfill_roster b
    CROSS JOIN LATERAL (
        SELECT 'phones' AS field, value, position
          FROM unnest(b.phones) WITH ORDINALITY AS t(value, position)
        UNION ALL
        SELECT 'emails', value, position
          FROM unnest(b.emails) WITH ORDINALITY AS t(value, position)
        UNION ALL
        SELECT 'urls', value, position
          FROM unnest(b.urls) WITH ORDINALITY AS t(value, position)
        UNION ALL
        SELECT 'source_urls', value, position
          FROM unnest(b.source_urls) WITH ORDINALITY AS t(value, position)
    ) listed
    WHERE NOT EXISTS (
        SELECT 1 FROM assertions a
         WHERE a.entity_type = 'person' AND a.entity_id = b.person_id
           AND a.field_path = listed.field AND a.kind = 'accept'
           AND a.withdrawn_at IS NULL AND a.value = to_jsonb(listed.value)
    );

    INSERT INTO source_records
        (id, changeset_id, jurisdiction_ocdid, name, other_names, label, source_url, url,
         phone, email, image, cdn_image, start_date, end_date, organization_id, created_at)
    SELECT md5('215:' || b.membership_id)::uuid,
           md5('215:' || b.jurisdiction_ocdid)::uuid,
           b.jurisdiction_ocdid, b.name,
           coalesce(array(
               SELECT name FROM unnest(b.other_names) AS name
                WHERE NOT EXISTS (
                    SELECT 1 FROM assertions a
                     WHERE a.entity_type = 'person' AND a.entity_id = b.person_id
                       AND a.field_path = 'other_names' AND a.kind = 'accept'
                       AND a.withdrawn_at IS NULL AND a.value = to_jsonb(name)
                )
           ), '{}'),
           b.label, b.source_url,
           (SELECT value FROM backfill_values v
             WHERE v.membership_id = b.membership_id AND v.field = 'urls' AND v.slot = 1),
           (SELECT value FROM backfill_values v
             WHERE v.membership_id = b.membership_id AND v.field = 'phones' AND v.slot = 1),
           (SELECT value FROM backfill_values v
             WHERE v.membership_id = b.membership_id AND v.field = 'emails' AND v.slot = 1),
           CASE WHEN EXISTS (
               SELECT 1 FROM assertions a
                WHERE a.entity_type = 'person' AND a.entity_id = b.person_id
                  AND a.field_path = 'image' AND a.kind = 'accept'
                  AND a.withdrawn_at IS NULL
           ) THEN NULL ELSE b.image END,
           CASE WHEN EXISTS (
               SELECT 1 FROM assertions a
                WHERE a.entity_type = 'person' AND a.entity_id = b.person_id
                  AND a.field_path = 'cdn_image' AND a.kind = 'accept'
                  AND a.withdrawn_at IS NULL
           ) THEN NULL ELSE b.cdn_image END,
           b.start_date, b.end_date, b.organization_id,
           b.first_seen_at - interval '1 second'
    FROM backfill_roster b
    ON CONFLICT (id) DO NOTHING;

    -- Each further list value as its own line of the same page.
    INSERT INTO source_records
        (id, changeset_id, jurisdiction_ocdid, name, other_names, label, source_url, url,
         phone, email, organization_id, created_at)
    SELECT md5('215:' || b.membership_id || ':' || v.field || ':' || v.value)::uuid,
           md5('215:' || b.jurisdiction_ocdid)::uuid,
           b.jurisdiction_ocdid, b.name, '{}', b.label,
           CASE WHEN v.field = 'source_urls' THEN v.value ELSE b.source_url END,
           CASE WHEN v.field = 'urls' THEN v.value END,
           CASE WHEN v.field = 'phones' THEN v.value END,
           CASE WHEN v.field = 'emails' THEN v.value END,
           b.organization_id,
           b.first_seen_at - interval '1 second' + v.slot * interval '1 microsecond'
    FROM backfill_roster b
    JOIN backfill_values v ON v.membership_id = b.membership_id
    WHERE b.carries_extras AND v.slot > 1
    ON CONFLICT (id) DO NOTHING;

    INSERT INTO source_record_identities (source_record_id, person_id)
    SELECT md5('215:' || membership_id)::uuid, person_id
    FROM backfill_roster
    UNION ALL
    SELECT md5('215:' || v.membership_id || ':' || v.field || ':' || v.value)::uuid, v.person_id
    FROM backfill_values v
    JOIN backfill_roster b USING (membership_id)
    WHERE b.carries_extras AND v.slot > 1
    ON CONFLICT (source_record_id) DO NOTHING;
    GET DIAGNOSTICS inserted = ROW_COUNT;

    DROP TABLE IF EXISTS backfill_values;
    DROP TABLE IF EXISTS backfill_roster;
    RETURN inserted;
END;
$$;

SELECT pg_temp.backfill_source_records();

COMMIT;
