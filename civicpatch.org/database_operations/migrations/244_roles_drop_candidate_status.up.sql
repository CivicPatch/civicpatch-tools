-- `candidate` is gone: a role is listed in a config file (active) or not (inactive). Nothing set
-- it, and readers already matched only active roles, so any left become inactive.

BEGIN;

UPDATE roles SET status = 'inactive' WHERE status = 'candidate';

ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_status_check;
ALTER TABLE roles ADD CONSTRAINT roles_status_check CHECK (
    status IN ('active', 'inactive')
);

COMMIT;
