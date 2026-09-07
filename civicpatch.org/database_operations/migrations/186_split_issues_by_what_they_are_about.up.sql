-- `issues` held two different things behind one polymorphic reference.
--
-- A pipeline-run issue says a *run* went wrong — it errored, stopped at its spend cap, or came
-- back short. A review issue says something about a *proposal* a human is looking at. They have
-- different subjects, different audiences and different lifetimes, and one table meant neither
-- could name its subject: `changeset_ids text[]` held a changeset id, or a pipeline-run id when
-- the scrape died before minting one, as text, with no foreign key either way.
--
-- The cost of that landed on the scrape-dispatch path. `jurisdiction_ocdids_with_pending_issues`
-- joins `changesets.id::text = ANY(pi.changeset_ids)` — a cast and an array scan, which no index
-- can serve, planned as a nested loop over every changeset. Split, each side gets a real foreign
-- key, and the run side reaches a jurisdiction without touching `changesets` at all, because
-- `pipeline_runs.jurisdiction_ocdid` is a column.
--
-- The array itself was never many. Migration 063 added it for `unrecognized_role`, which keyed on
-- the *role name* and so legitimately spanned changesets across the fleet; that type has since
-- been retired, and unmatched roles are carried on `memberships.unmatched_text` instead. Every
-- surviving type keys on something containing its own subject, so the `array_agg(DISTINCT ...)`
-- merge branch became unreachable: a second subject means a different key, which means a
-- different row. Every row in dev holds exactly one id.
--
-- `issue_key` and the `(issue_type, issue_key)` uniqueness go with it. A recurring problem files
-- a fresh row per run and is dismissed again, which is what it did already — each run mints its
-- own changeset, so the key differed every time and the constraint never collapsed anything
-- across runs. What is kept is idempotency *within* one subject: one issue of a type per run, so
-- a retried activity refreshes rather than duplicates.

BEGIN;

CREATE TABLE IF NOT EXISTS pipeline_run_issues (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- The run is always there for these: every scrape changeset has one (108 of 108 in dev),
    -- and a scrape that died before ingest has a run and no changeset — which is the case the
    -- old polymorphism existed for. The changeset, when there is one, is one join away via
    -- `pipeline_runs.changeset_id`.
    --
    -- Scrapes are the only source today. A sheet import reports its problems in the import
    -- preview (`jurisdictions_blocked`), which has no lifecycle and never reaches this table —
    -- so if imports ever need issues, that is a decision to make then, not a nullable column
    -- to carry until it happens.
    pipeline_run_id uuid NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    issue_type      text NOT NULL,
    data            jsonb NOT NULL DEFAULT '{}'::jsonb,
    status          text NOT NULL DEFAULT 'pending',
    resolved_at     timestamptz,
    is_flagged      boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS changeset_issues (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    changeset_id uuid NOT NULL REFERENCES changesets(id) ON DELETE CASCADE,
    issue_type   text NOT NULL,
    data         jsonb NOT NULL DEFAULT '{}'::jsonb,
    status       text NOT NULL DEFAULT 'pending',
    resolved_at  timestamptz,
    is_flagged   boolean NOT NULL DEFAULT false,
    created_at   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE pipeline_run_issues DROP CONSTRAINT IF EXISTS pipeline_run_issues_status_check;
ALTER TABLE pipeline_run_issues ADD CONSTRAINT pipeline_run_issues_status_check
    CHECK (status IN ('pending', 'resolved', 'superseded'));
ALTER TABLE changeset_issues DROP CONSTRAINT IF EXISTS changeset_issues_status_check;
ALTER TABLE changeset_issues ADD CONSTRAINT changeset_issues_status_check
    CHECK (status IN ('pending', 'resolved', 'superseded'));

-- One issue of a type per *run*, so a retried activity refreshes instead of duplicating. Not
-- the old cross-subject dedupe: a new run is a new row, and the same problem recurring is meant
-- to be filed and dismissed again.
CREATE UNIQUE INDEX IF NOT EXISTS pipeline_run_issues_one_per_type
    ON pipeline_run_issues (pipeline_run_id, issue_type);

-- Deliberately no equivalent on `changeset_issues`. A run reporting the same fault twice is one
-- fault; a person reporting two things about one roster is two reports. Adding the index here
-- collapsed five user reports into three on the first backfill.
CREATE INDEX IF NOT EXISTS changeset_issues_changeset_idx ON changeset_issues (changeset_id);

-- What the candidate query reads.
CREATE INDEX IF NOT EXISTS pipeline_run_issues_pending_idx
    ON pipeline_run_issues (status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS changeset_issues_pending_idx
    ON changeset_issues (status) WHERE status = 'pending';

-- Backfill. A run-side row reaches its run directly when the old id was a run's, and through
-- `pipeline_runs.changeset_id` when it was a changeset's. DISTINCT ON keeps the newest of any
-- rows that collapse onto one subject under the new uniqueness.
INSERT INTO pipeline_run_issues
    (pipeline_run_id, issue_type, data, status, resolved_at, is_flagged, created_at)
SELECT DISTINCT ON (run_id, issue_type)
       run_id, issue_type, data, status, resolved_at, is_flagged, created_at
FROM (
    SELECT COALESCE(direct.id, viachangeset.id) AS run_id,
           i.issue_type, i.data, i.status, i.resolved_at, i.is_flagged, i.created_at
    FROM issues i
    LEFT JOIN pipeline_runs direct       ON direct.id::text = i.changeset_ids[1]
    LEFT JOIN pipeline_runs viachangeset ON viachangeset.changeset_id::text = i.changeset_ids[1]
    WHERE i.issue_type NOT IN ('user_reported', 'merge_failed')
) resolved
WHERE run_id IS NOT NULL
ORDER BY run_id, issue_type, created_at DESC
ON CONFLICT DO NOTHING;

-- `merge_failed` is not carried across. Nothing has been able to raise one since 2026-09-04,
-- when rosters moved to committing straight to `main` and the roster-PR era was swept out —
-- no writer and no backend reader survive, only frontend branches for a type that cannot
-- occur. The name outlived the mechanism too: there is no merge, there is a commit.
INSERT INTO changeset_issues
    (changeset_id, issue_type, data, status, resolved_at, is_flagged, created_at)
SELECT c.id, i.issue_type, i.data, i.status, i.resolved_at, i.is_flagged, i.created_at
FROM issues i
JOIN changesets c ON c.id::text = i.changeset_ids[1]
WHERE i.issue_type = 'user_reported';

DROP TABLE IF EXISTS issues;

COMMIT;
