-- `pipeline_runs.request_id` was UNIQUE NOT NULL and every request had exactly one run: a
-- vertical partition of one entity, not a relationship. 21 queries joined the two.
--
-- Named for the ask, not the machine: a scrape is one producer, and a Google Sheets import and
-- a manual jurisdiction edit are others that never run a pipeline. `run_*` is null for those,
-- which reads correctly — nobody ran anything.
--
-- Every event on a request already has its own timestamp — `created_at` for the ask,
-- `published_at` and `dismissed_at` for the decision — so a generic `updated_at` had nothing
-- left to mean, and no writer. It goes; the run's clock arrives named for its own event.
--
-- `sourced_at` joins the `source_*` family — `source_records`, `source_urls`,
-- `source_labels` — because it is that layer's clock: when the source was last read. The `_at`
-- suffix pins it to our time rather than the source's, as `_date` does the reverse throughout.
-- It is what dates `last_seen_at` on every membership, and what supersede orders on — *which
-- scrape read the source more recently*, never which row was touched.
--
-- No `run_` prefix. The vocabulary collision the split guarded against needed *two* status
-- columns in two tables; one table can only have the one.
--
-- `id`/`jobs_id_seq` goes: `requests.id` was always the identity — `request_id` is the FK name
-- in source_records, change_logs and the 117 backup.
--
-- `github_run_id` goes, and the handshake around it goes with it. Its only consumer was
-- `worker`'s `trigger_github_action`, which polled `/pipeline_runs/{id}/run` until a run id
-- appeared and then **discarded it** — the caller never read the return. So it bought a
-- barrier, not information, and `poll_pipeline_run_status` reaches the same point by watching
-- `requests.status`.
--
-- ⚠️ CROSS-REPO: `data_scrape.yml` in **CivicPatch/server** still POSTs its run id to
-- `/pipeline_runs/{id}/run`, which now 404s. That step has to be removed there too — if it
-- fails the job on a non-2xx, remote scrapes break. Nothing in this repo can verify it.
BEGIN;

ALTER TABLE requests ADD COLUMN IF NOT EXISTS status text;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS progress integer;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS sourced_at timestamptz;

UPDATE requests r
   SET status = pr.status,
       progress = pr.progress,
       sourced_at = pr.updated_at
  FROM pipeline_runs pr
 WHERE pr.request_id = r.id;

CREATE INDEX IF NOT EXISTS idx_requests_status ON requests (status);

ALTER TABLE requests DROP COLUMN IF EXISTS updated_at;

DROP TABLE IF EXISTS pipeline_runs;

COMMIT;
