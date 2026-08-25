-- How far behind prod's schema is, and when it last moved.
--
--   cd ~/cp-infrastructure
--   mise run prod-sql < ~/civicpatch-tools/civicpatch.org/database_operations/queries/migrations_pending.sql
--
-- Compare `newest_applied` against the highest-numbered file in
-- `civicpatch.org/database_operations/migrations/`. Everything above it applies at the next
-- pod start, in one go — migrations run from the container entrypoint, so a deploy is also a
-- schema change whether or not anyone meant it to be.
--
-- `last_applied_at` is the useful one when the gap is large: it says how long this has been
-- accumulating, and therefore how much runs at once on the next rollout.
SELECT
    count(*)                    AS applied_total,
    max(version)                AS newest_applied,
    max(applied_at)::date       AS last_applied_at,
    (SELECT string_agg(version, ', ' ORDER BY version)
     FROM (SELECT version FROM schema_migrations ORDER BY applied_at DESC LIMIT 5) recent)
                                AS five_most_recent
FROM schema_migrations;
