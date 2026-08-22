BEGIN;

-- Two fields marked as ours, because a consumer dropping every `_*` key must be left holding
-- a conforming Popolo Post. Stored extensions carry the prefix as their column name, so the
-- name is the same in the schema, the query and the JSON; a computed one like `_is_verified`
-- cannot, and takes an alias instead.

-- Whether a roster omitting this post means anything. A tracked post is one we diff against:
-- `close_absent` records that we stopped seeing its holder either way, but the review queue
-- and the post issues (unbuilt) will read this before asking anyone to look.
--
-- Orthogonal to lifecycle, which `posts` does not model yet. An occupied post may be
-- untracked: a City Attorney is real and currently filled, and calling that "retired" to
-- express "we do not diff it" would be a lie. Whoever adds `posts.status` should leave this
-- alone rather than fold it in.
--
-- This is what replaces excluding a person whose labels resolve to no role. That drop could
-- not distinguish out-of-scope ("Police Chief") from in-scope-but-unrecognised ("Selectman"),
-- and recorded neither. Scope belongs on the post, where it can differ per jurisdiction — a
-- clerk is elected in some towns and appointed in others. Tracked until a person says
-- otherwise: guessing from the role would be a second exclusion rule, quieter than the first.
--
-- `is_` because it is a boolean, as `issues.is_flagged` is. Defaults true, so every existing
-- post keeps behaving exactly as it does today.
ALTER TABLE posts ADD COLUMN _is_tracked boolean NOT NULL DEFAULT true;

COMMENT ON COLUMN posts._is_tracked IS
    'A roster omitting this post is meaningful. Orthogonal to lifecycle: an occupied post may be untracked.';

-- Popolo's Post has no headcount: one Post is one position there, while ours is a group of
-- interchangeable seats, because a source listing five at-large councillors gives no way to
-- tell seat 3 from seat 4. That divergence is what the prefix marks.
ALTER TABLE posts RENAME COLUMN headcount TO _headcount;

COMMIT;
