-- Two cuts to 118, neither of which loses a guarantee anything relies on.
--
-- 1 · `posts.status` goes. It carried two independent facts in one enum — whether the seat
--     still exists, and whether a human vouched for it — so it could express neither
--     "confirmed, since retired" nor "guessed, still appearing", and both occur.
--
--     Nothing replaces it. Verification is derivable, because memberships are written only at
--     publish and publishing is a named human act:
--
--         EXISTS (SELECT 1 FROM memberships m WHERE m.post_id = p.id)
--
--     A post with a member was endorsed by a person; one without was only ever proposed by a
--     scrape. No column, no table, no backfill.
--
--     Safe to drop outright: `candidate` is the only value in practice. `find_or_create`
--     mints it and nothing anywhere promotes a post — the sole reference to 'active' is the
--     WHERE in `posts.unseen_since`, which therefore can never return a row.
--
-- 2 · The posts -> organizations composite FK goes, with the redundant unique index that
--     existed only to enable it.
--
--     `organizations_jurisdiction_ocdid_id_key` enforces nothing on its own: `id` is already
--     the primary key, so any pair containing it is unique. Postgres just requires a matching
--     unique constraint before a composite FK can be declared, so it is syntax tax paid on
--     every insert.
--
--     What it bought was "a post's jurisdiction matches its organization's". Worth keeping if
--     a breach were silent — but it is not. A mismatched post surfaces in the wrong
--     jurisdiction's list, where somebody sees it. Both columns are written by one code path,
--     in one transaction, from one derived object.
--
-- The memberships -> posts composite FK **stays**, deliberately. Its failure mode is the
-- silent one: `memberships.organization_id` cannot be a join away, because the partial index
-- `(person_id, organization_id) WHERE closed_at IS NULL` needs it local and a partial unique
-- index cannot span tables. If that column ever disagreed with its post's organization, the
-- "one open seat per body" rule would quietly guard the wrong rows — a person holding two
-- open memberships in one real body, or blocked across two. Keep the guard whose failure
-- corrupts another constraint; drop the guard whose failure is merely visible.
--
-- `posts.jurisdiction_ocdid` stays as a column. It is queried directly by `find_or_create`,
-- `unseen_since` and `list_for_jurisdiction`; removing it would cost a join in all three to
-- save a denormalisation nothing gets wrong.

BEGIN;

ALTER TABLE posts
    DROP CONSTRAINT IF EXISTS posts_jurisdiction_ocdid_organization_id_fkey;

ALTER TABLE organizations
    DROP CONSTRAINT IF EXISTS organizations_jurisdiction_ocdid_id_key;

ALTER TABLE posts
    DROP COLUMN IF EXISTS status;

COMMIT;
