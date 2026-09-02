BEGIN;

-- Back to nulls, then the row. Only rows attributed to the system are touched, so a write a
-- person actually made survives the rollback.
UPDATE changesets
SET resolved_by_user_id = NULL
WHERE resolved_by_user_id = '00000000-0000-4000-8000-000000000001';

UPDATE changesets
SET created_by_user_id = NULL
WHERE created_by_user_id = '00000000-0000-4000-8000-000000000001';

UPDATE change_logs
SET user_id = NULL
WHERE user_id = '00000000-0000-4000-8000-000000000001';

DELETE FROM users WHERE id = '00000000-0000-4000-8000-000000000001';

COMMIT;
