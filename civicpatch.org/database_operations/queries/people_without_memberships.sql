-- Who loses their office when `people.data` is dropped.
--
-- The people behind `office_would_go_null` in `people_data_droppable.sql`. They hold no
-- membership, open or closed, so there is no post to fall back to and the only record of what
-- they were is the blob. Dropping the column destroys it rather than hiding it.
--
-- Judge the list. Stale seed rows are a shrug. A recently-touched active person is a backfill:
-- mint their post and a closed membership before the migration, not after.
--
--   cd ~/cp-infrastructure
--   mise run prod-sql < ~/civicpatch-tools/civicpatch.org/database_operations/queries/people_without_memberships.sql
--
-- dev: 25 rows — 2025-vintage seeds (Ventura, Boise, St Anthony, Algona, Buckley) plus one
-- inactive Seattle city attorney.
SELECT
    people.updated_at::date         AS last_touched,
    people.status,
    people.jurisdiction_ocdid,
    people.name,
    people.data->'office'->>'name'  AS office_name
FROM people
WHERE NOT EXISTS (SELECT 1 FROM memberships m WHERE m.person_id = people.id)
ORDER BY people.updated_at DESC
LIMIT 100;
