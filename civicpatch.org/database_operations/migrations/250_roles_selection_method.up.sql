-- How each role's office is filled, mirroring open-data's `selection_method` (SelectionMethod in
-- shared/schemas.py). The fold reads it: only elected_by_voters roles win a post. The default
-- is today's behaviour, every role a post, until the next config sync writes each role's value.

BEGIN;

ALTER TABLE roles ADD COLUMN IF NOT EXISTS selection_method text NOT NULL DEFAULT 'elected_by_voters';

ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_selection_method_check;
ALTER TABLE roles ADD CONSTRAINT roles_selection_method_check CHECK (
    selection_method IN ('elected_by_voters', 'elected_by_members', 'appointed')
);

COMMIT;
