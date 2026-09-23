BEGIN;

-- 136 made `name` NOT NULL once the old `data` column was retired, on the assumption that
-- every person the writer saw had a name. The fold does not. Clearing a person's name in the
-- editor files a `name` reject and no accept (`core/people_edits.py`: `was and now in (None,
-- "")`), so `scalar_value` finds every name their records carry rejected and answers None,
-- while the person stays on the roster because a live record still names them. The writer has
-- to persist what the fold derives (R4, R6), so the column admits NULL again.
ALTER TABLE people ALTER COLUMN name DROP NOT NULL;

COMMIT;
