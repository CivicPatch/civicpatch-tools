-- Reverses 120. The index goes with the column, so dropping the column alone would leave a
-- dangling name if the column drop were ever made conditional.

BEGIN;

DROP INDEX IF EXISTS memberships_role_id_idx;

ALTER TABLE memberships
    DROP COLUMN IF EXISTS role_id;

COMMIT;
