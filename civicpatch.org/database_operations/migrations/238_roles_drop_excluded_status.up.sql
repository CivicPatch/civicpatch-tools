-- `excluded` is gone: its roles become ordinary active roles, ranked below every other role.

BEGIN;

UPDATE roles
SET priority = ranked.new_priority
FROM (
    SELECT id, row_number() OVER (ORDER BY status = 'excluded', priority) - 1 AS new_priority
    FROM roles
    WHERE priority IS NOT NULL
) AS ranked
WHERE roles.id = ranked.id;

UPDATE roles SET status = 'active' WHERE status = 'excluded';

ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_status_check;
ALTER TABLE roles ADD CONSTRAINT roles_status_check CHECK (
    status IN ('active', 'candidate', 'inactive')
);

COMMIT;
