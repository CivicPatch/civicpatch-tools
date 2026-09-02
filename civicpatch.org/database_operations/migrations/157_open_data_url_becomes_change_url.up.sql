-- `changesets.open_data_url` becomes `change_url`. Pure rename: nothing added, dropped or
-- retyped.
--
-- The column has always held a commit url *or* a pull request url, and `DATABASE.md` documented
-- both — which is the point: the old name says which *repo* the thing is in, not what it is. A
-- commit and a pull request are both "the change", so the name stays true whichever a row holds.
--
-- **Known cost, accepted**: it stutters as `changesets.change_url`. That buys one vocabulary —
-- the entity is a changeset and so is the thing the url points at, so there is no second noun to
-- learn. Rejected: `submission_url` (a second noun for the entity just named), `reference_url`
-- (reads as a sibling of `source_records.source_url`, which points the opposite direction),
-- `artifact_url` (collides with the pipeline's bucket), bare `url` (taken twice already),
-- `commit_url` / `landed_url` (false for an open PR), `published_url` (set before publishing
-- under the PR flow), `upstream_url` (implies a repo we do not own).
--
-- **Idempotency**: postgres has no `IF EXISTS` for `RENAME COLUMN`, so it is guarded on the
-- catalog, matching 152 and 156.
BEGIN;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'changesets'
                 AND column_name = 'open_data_url') THEN
        ALTER TABLE changesets RENAME COLUMN open_data_url TO change_url;
    END IF;
END $$;

COMMIT;
