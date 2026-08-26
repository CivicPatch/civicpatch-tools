-- Two column types that were wrong for what they hold.
--
-- 1. Term dates belong to the tenure, not the human: Popolo puts start_date/end_date on
--    Membership and gives Person only birth_date/death_date. `text`, not `date`, matching
--    `people` and for the same reason — sources give partial dates and Popolo allows them.
--    Of dev's 4,559 start dates only 1,037 are full, and `'2024'::date` is an error.
--    `people` keeps its columns until every reader has moved.
--
-- 2. `source_record_identities.person_id` is a cluster id and every other one is a uuid. As
--    text it accepted `_resolution`'s ambiguous-match sentinel, `":".join(...)`: the row
--    inserted cleanly, the request satisfied AVAILABLE_FOR_REVIEW ("has sightings"), and the
--    card reached the pool with a broken cluster id. Failing at the insert is the better
--    failure. No FK to `people` — ids are minted at ingest for people nobody matched, whose
--    row does not exist until publish. Unconvertible rows are dropped, not repaired: this is
--    the *linkage* 140 separated from the evidence so re-resolution could rewrite it, and the
--    sighting survives in `source_records`.
BEGIN;

ALTER TABLE memberships ALTER COLUMN start_date TYPE text USING start_date::text;
ALTER TABLE memberships ALTER COLUMN end_date TYPE text USING end_date::text;

UPDATE memberships m
   SET start_date = COALESCE(m.start_date, p.start_date),
       end_date   = COALESCE(m.end_date, p.end_date)
  FROM people p
 WHERE m.person_id = p.id
   AND (p.start_date IS NOT NULL OR p.end_date IS NOT NULL);

-- `::text` so this works whichever type the column currently is: re-running a migration has
-- to be a no-op, and `!~` does not exist for uuid.
DELETE FROM source_record_identities
 WHERE person_id::text !~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$';

ALTER TABLE source_record_identities
    ALTER COLUMN person_id TYPE uuid USING person_id::uuid;

COMMIT;
