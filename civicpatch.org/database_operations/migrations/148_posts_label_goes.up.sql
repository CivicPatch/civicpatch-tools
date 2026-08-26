-- `posts.label` was a stored copy of a pure function. Measured before dropping: of 11,775
-- posts, **11,763 held a byte-identical copy of `derive_post_label(role.label, division)`**,
-- 11 were null, and exactly one differed — a lowercase slug typed by hand while somebody was
-- exercising the post editor. So no human has ever authored a label the derivation could not
-- produce, and the column cost is a stale copy that never self-corrects: a label is written at
-- mint and only a person may change it, so a taxonomy fix never reaches it.
--
-- It goes, and the label is composed on read from the same function. Popolo's `Post.label` is
-- still served, computed rather than stored.
--
-- ⚠️ What this closes: naming a seat something the derivation cannot express — "Council
-- Member, At-Large Seat 3". Nobody has, but the door shuts. Reopening it means a new column
-- that is null unless a human writes it, which is what this one should have been.
BEGIN;

ALTER TABLE posts DROP COLUMN IF EXISTS label;

COMMIT;
