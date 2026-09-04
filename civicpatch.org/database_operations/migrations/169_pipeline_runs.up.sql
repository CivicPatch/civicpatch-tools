-- A run is an attempt; a changeset is a proposal. This is the attempt.
--
-- They were one row from migration 147, which merged `pipeline_runs` into `requests` on the
-- grounds that "every request had exactly one run: a vertical partition of one entity". True
-- then — every request *was* a scrape. 149 added `sheet_import`, 153 added `people_edit` and
-- `jurisdiction_edit`, and the premise expired six migrations later. Since then `status` has
-- been NULL on every row that is not a scrape, and `created_at` has meant *request* time for a
-- scrape and *content* time for everything else — up to two days apart.
--
-- What actually forces the split is cost tracking, which is coming: a run that dies at step four
-- has already spent on steps one to three. Spend is per attempt, and attempts outnumber
-- proposals, so a failed run needs a durable identity or its cost cannot be attributed to a
-- jurisdiction, a state or a month. `created_at` here therefore predates any spend.
--
-- One `status` column, not a `step`/`outcome` pair. It holds twelve progress names and then a
-- terminal one, which is how `runners/people_collector/transitions/main.py` already models it.
-- The reason it was confusing was never that it held two things — it was that *changeset*
-- readers had to know which they were looking at. Here every reader is run-aware.
--
-- Backfill reuses the changeset id as the run id so a scrape in flight during the deploy keeps
-- answering `/api/v1/pipeline_runs/{id}/status` — an endpoint already named for runs and keyed
-- by changeset. New runs get their own id and the trigger passes that instead.
--
-- Additive: no changeset is deleted or re-pointed, so `change_logs`, `issues` and
-- `review_session_entries` are untouched and history reads the same afterwards.
--
-- No indexes. 101 rows, and the readers are `finished_at IS NULL` and a jurisdiction lookup,
-- both of which a seq scan answers instantly at this size. Add one when a query is measured to
-- want it — the same call migration 164 made about `changesets.state`.

BEGIN;

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                 uuid PRIMARY KEY,
    jurisdiction_ocdid text NOT NULL,
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    status             text,
    progress           integer,
    -- Who asked for the scrape. A fact about the attempt: the changeset it may go on to
    -- produce is minted by the system at ingest, not by a person.
    created_by_user_id uuid,
    arguments_json     jsonb NOT NULL DEFAULT '{}'::jsonb,
    finished_at        timestamptz,
    changeset_id       uuid REFERENCES changesets(id) ON DELETE SET NULL
);

-- One run per scrape that exists today. Only scrapes ever carried a status: measured 2026-09-04,
-- 101 of 101.
INSERT INTO pipeline_runs (
    id, jurisdiction_ocdid, created_at, updated_at,
    status, progress, created_by_user_id, arguments_json, finished_at, changeset_id
)
SELECT c.id, c.jurisdiction_ocdid, c.created_at, c.updated_at,
       c.status, c.progress, c.created_by_user_id, COALESCE(c.arguments_json, '{}'::jsonb),
       -- A run that reached a terminal status finished when it last reported.
       CASE WHEN c.status IN ('SUCCESS', 'ERROR', 'CANCELLED', 'RESOLVED')
            THEN c.updated_at END,
       c.id
FROM changesets c
WHERE c.kind = 'scrape'
ON CONFLICT (id) DO NOTHING;

COMMIT;
