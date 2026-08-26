-- Restores the columns and the values, from the memberships 144 filled. Not every row comes
-- back: a person with no membership had nowhere for the date to be copied to, which is the
-- same 21 people 144 could not reach.
BEGIN;

ALTER TABLE people ADD COLUMN IF NOT EXISTS start_date text;
ALTER TABLE people ADD COLUMN IF NOT EXISTS end_date text;

UPDATE people p
   SET start_date = m.start_date,
       end_date = m.end_date
  FROM memberships m
 WHERE m.person_id = p.id
   AND (m.start_date IS NOT NULL OR m.end_date IS NOT NULL);

COMMIT;
