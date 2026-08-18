-- Exact reverse of 118. Dropped in FK order; indexes and constraints go with their tables.
-- Idempotent: DROP ... IF EXISTS is a no-op when 118 was never applied.
--
-- roles.is_unique is untouched here because 118 does not drop it — the derivation needs it
-- to seed posts.headcount, and it is removed by a later migration once that has run.
BEGIN;

DROP TABLE IF EXISTS memberships;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS divisions;
DROP TABLE IF EXISTS organizations;

DELETE FROM roles WHERE id = 'unmatched';

COMMIT;
