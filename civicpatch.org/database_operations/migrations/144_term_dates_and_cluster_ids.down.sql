-- `person_id` back to text is lossless — every uuid is valid text. The rows the up migration
-- dropped are not restored: they held no recoverable id, only a sentinel saying the match was
-- ambiguous.
--
-- ⚠️ The term dates are not. `date` cannot hold "2024" or "2024-05", which is most of what
-- sources give, so going back drops every partial date rather than failing with half the rows
-- converted. Full dates survive, and `people` still holds the originals — re-running the up
-- restores what it can.
BEGIN;

ALTER TABLE source_record_identities
    ALTER COLUMN person_id TYPE text USING person_id::text;

ALTER TABLE memberships
    ALTER COLUMN start_date TYPE date
    USING CASE WHEN start_date::text ~ '^\d{4}-\d{2}-\d{2}$' THEN start_date::text::date END;
ALTER TABLE memberships
    ALTER COLUMN end_date TYPE date
    USING CASE WHEN end_date::text ~ '^\d{4}-\d{2}-\d{2}$' THEN end_date::text::date END;

COMMIT;
