-- `memberships.label` held two different things joined into one string. Split them, because
-- they have different readers.
--
--   designations     how the source tells one seat from another — "Place 2", "Position 8".
--                    Texas cities name at-large seats Place 1..6; Washington uses Position
--                    1..7. Belongs beside the person, and is the thing a roster screen shows.
--
--   unmatched_text  what the parser could not classify — "Board", "Zoning Administrator".
--                    Triage material, and the source of the cross-jurisdiction unmatched list
--                    Phase 4 wants. Joined into one string it was unreadable: a label giving
--                    'Zoning Administrator' and 'Ordinance Officer' means two separate things
--                    to look at, not one term called "Zoning Administrator Ordinance Officer".
--
-- Both are arrays because both are genuinely multi-valued: measured over open-data
-- 2026-08-18, 19 records carry two designations and 32 carry two or three unmatched runs.
--
-- Nothing is migrated from `label`. It was written by one scrape cycle in dev and by nothing
-- in production — posts and memberships have never published there — so there is no data to
-- preserve, and re-deriving from `source_records` is free anyway: `derived_posts` is pure and
-- the evidence is append-only.

BEGIN;

ALTER TABLE memberships
    ADD COLUMN IF NOT EXISTS designations text[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS unmatched_text text[] NOT NULL DEFAULT '{}';

ALTER TABLE memberships
    DROP COLUMN IF EXISTS label;

-- The triage read: every unmatched term across every jurisdiction, which is a scan without
-- this. GIN because the query is containment, not equality.
CREATE INDEX IF NOT EXISTS memberships_unmatched_text_idx
    ON memberships USING gin (unmatched_text);

COMMIT;
