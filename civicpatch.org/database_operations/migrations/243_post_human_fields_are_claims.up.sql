BEGIN;

-- Headcount and tracked are read from claims now (`database/posts.py`), so a post row is only
-- its key and deleting one loses nothing. No backfill: prod's 4,111 headcounts with no claim
-- were counts the old derivation observed, not anyone's edit, and every tracked value differing
-- from the default already has a claim.
ALTER TABLE posts DROP CONSTRAINT IF EXISTS posts_headcount_check;
ALTER TABLE posts DROP COLUMN IF EXISTS meta_headcount;
ALTER TABLE posts DROP COLUMN IF EXISTS meta_is_tracked;

COMMIT;
