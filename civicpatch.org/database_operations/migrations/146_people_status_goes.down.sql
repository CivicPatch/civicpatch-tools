-- Restores the column and recomputes it from memberships, which is what it always mirrored.
-- ⚠️ Not byte-identical: the 20 people with no membership come back `inactive`, where they
-- were `active` before. That difference is the drift the column allowed.
BEGIN;

ALTER TABLE people ADD COLUMN IF NOT EXISTS status text DEFAULT 'active';

UPDATE people p
   SET status = CASE
       WHEN EXISTS (
           SELECT 1 FROM memberships m
           WHERE m.person_id = p.id AND m.closed_at IS NULL
       ) THEN 'active' ELSE 'inactive' END;

ALTER TABLE people ADD CONSTRAINT people_status_check
    CHECK (status = ANY (ARRAY['active'::text, 'inactive'::text]));

COMMIT;
