-- Restores the value, not the rows — and says so rather than guessing.
--
-- Once these are publishes they are indistinguishable from any other publish that moved no
-- roster: only 2 of the 6 carry a `dismiss_review` log, because `dismiss_request` did not always
-- write one, so there is no predicate that selects exactly them. Re-dismissing every empty
-- publish would swallow unrelated rows.
--
-- Widening the CHECK is the reversible half, and it is the half that matters: it lets the old
-- code write `unchanged` again. The column comment goes back to 133's wording verbatim.

BEGIN;

ALTER TABLE changesets DROP CONSTRAINT IF EXISTS changesets_dismissed_reason_valid;
ALTER TABLE changesets ADD CONSTRAINT changesets_dismissed_reason_valid
    CHECK (dismissed_reason IS NULL
           OR dismissed_reason IN ('rejected', 'cancelled', 'errored', 'superseded', 'unchanged'));

COMMENT ON COLUMN changesets.dismissed_reason IS
    'Why the request left the pool: superseded (discarded unread) | unchanged (roster confirmed). NULL = human or pre-dating this column.';

COMMIT;
