BEGIN;

-- Scrape-freshness engine, step 1 (plan: .scratch/2026-06-10-plan-scrape-freshness-redesign.md).
-- Lands all DB structure for retiring jurisdictions_metadata.yml's `updated_at`, which today
-- conflates three jobs. This migration is inert on day one: pure structure + a backfill that
-- preserves existing freshness. Behavior only changes once the sync/stamping/candidate code lands.
--
--   * jurisdictions.scraped_at — "last *scraped*", stamped on job-PR merge (not manual edits)
--   * state_configs            — per-state tunable settings; min_scraped_at is the freshness floor
--   * synced_files             — last-synced blob SHA per file we tree-diff (sync cursors)

ALTER TABLE jurisdictions ADD COLUMN scraped_at TIMESTAMPTZ;

-- Powers both the per-state dashboard fraction and the candidate queue
-- (scraped_at IS NULL OR scraped_at < min_scraped_at), scoped by state.
CREATE INDEX jurisdictions_state_scraped_at_idx ON jurisdictions (state, scraped_at);

-- Per-state tunable settings. A jurisdiction counts as fresh when its scraped_at is at least
-- the state's min_scraped_at. Seeded at EPOCH so every backfilled scrape counts as fresh
-- and nothing mass-requeues; raising it is the deliberate way to launch a per-state re-scrape
-- campaign. Absolute (not rolling) keeps "completely scraped" a stable, monotonic state. Every
-- state always has exactly one row (the companion admin CRUD relies on this no-delete invariant).
CREATE TABLE state_configs (
    state              TEXT PRIMARY KEY,
    min_scraped_at TIMESTAMPTZ NOT NULL DEFAULT 'epoch'::timestamptz
);

-- Seed a row (at the epoch default) for every state that already has jurisdictions.
INSERT INTO state_configs (state)
SELECT DISTINCT state FROM jurisdictions WHERE state IS NOT NULL;

-- Sync cursors: the last-synced git blob SHA of every file we tree-diff — both the per-state
-- jurisdictions.yml and the per-jurisdiction people files, keyed by repo path. Starts empty; the
-- first new-sync run sees no stored SHA and fetches everything once. synced_at is the only record
-- of when a path last synced (sync liveness / debugging).
CREATE TABLE synced_files (
    path      TEXT PRIMARY KEY,
    blob_sha  TEXT NOT NULL,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Backfill scraped_at so day one reads current freshness instead of 0% everywhere
-- (which would mass-requeue paid LLM scrapes). Primary signal = latest merged PR for
-- the jurisdiction; fallback = latest people.updated_at (carries the scrape time).
-- Stays NULL only where neither exists → truly never-scraped → correctly queued.
-- One-time imprecision (accepted): the PR leg counts any merged PR, and the people
-- fallback is bumped by manual edits too; ongoing stamping is the clean job-PR path.
UPDATE jurisdictions j SET scraped_at = COALESCE(
    (SELECT max(pr.merged_at)
       FROM pull_requests pr JOIN requests r ON r.id = pr.request_id
      WHERE r.jurisdiction_ocdid = j.jurisdiction_ocdid AND pr.merged_at IS NOT NULL),
    (SELECT max(p.updated_at)
       FROM people p WHERE p.jurisdiction_ocdid = j.jurisdiction_ocdid)
);

COMMIT;
