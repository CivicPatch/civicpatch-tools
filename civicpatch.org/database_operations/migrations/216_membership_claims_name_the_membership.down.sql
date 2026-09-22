BEGIN;

-- The copies are the membership claims keyed by `membership_id(...)`, which never equals a
-- `memberships` row id; the originals, keyed by the row, stay.
DELETE FROM assertions
 WHERE entity_type = 'membership'
   AND NOT EXISTS (SELECT 1 FROM memberships m WHERE m.id = assertions.entity_id);

DROP EXTENSION IF EXISTS "uuid-ossp";

COMMIT;
