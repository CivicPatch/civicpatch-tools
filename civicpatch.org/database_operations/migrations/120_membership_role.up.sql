-- A title held in a seat somebody else's role defines.
--
-- `posts.role_id` says what the seat is. This says what the holder is *called* when the two
-- differ: a councilmember serving as mayor holds `council-member · district:2` and carries
-- `mayor` here. NULL in the ordinary case, where the post's own role is the whole story.
--
-- Why the role cannot stay on the post. A mayoralty selected by the council rotates between
-- districts, so keyed as `(role, division)` it mints a fresh post every cycle and strands the
-- last one — while the district's actual council seat never appears at all. Measured over
-- open-data 2026-08-18: 402 posts across 3,859 jurisdictions are titles of this kind, led by
-- mayor-pro-tempore (182), council-president (47), mayor (43) and vice-mayor (36). Posts fall
-- 13,393 -> 12,991 once they move here.
--
-- Nesting alone does not identify them. 215 mayors sit under a county — one per village — and
-- every one is a genuine seat. What decides it is whether the division's last segment names a
-- government (`place`, `county`) or an electoral division of one (`ward`, `council_district`).
-- `core/post_derivation.py` holds that rule.
--
-- Deliberately single-valued rather than an array: the titles are mutually exclusive, nobody
-- is both mayor and vice-mayor, and a plain FK to `roles` keeps the vocabulary shared with
-- `posts.role_id` instead of inventing free text beside it.

BEGIN;

ALTER TABLE memberships
    ADD COLUMN IF NOT EXISTS role_id text REFERENCES roles (id) ON UPDATE CASCADE;

-- Answers "who is the mayor" for the cities where the mayoralty is a title rather than an
-- office. Partial because the column is NULL for the overwhelming majority of rows.
CREATE INDEX IF NOT EXISTS memberships_role_id_idx
    ON memberships (role_id) WHERE role_id IS NOT NULL;

COMMIT;
