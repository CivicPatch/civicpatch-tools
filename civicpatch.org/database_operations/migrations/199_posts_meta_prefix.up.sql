BEGIN;

-- `_headcount`/`_is_tracked` used a leading underscore to mark "not civic data" (131).
-- Spelling that out as `meta_` instead reads the same way on the wire and in SQL without
-- relying on a symbol a skimming reader can miss. `_is_verified` is computed, not stored
-- (POST_IS_VERIFIED in database/posts.py), so it needs no column rename — only its query
-- alias changes.
ALTER TABLE posts RENAME COLUMN _headcount TO meta_headcount;
ALTER TABLE posts RENAME COLUMN _is_tracked TO meta_is_tracked;

COMMIT;
