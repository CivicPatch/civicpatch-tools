-- The pages a scrape fetched, one row per url per run: the index into the debug bucket, the
-- hash gate's memory, and a fact the fold reads (organization_ids is what a row is a read of).
-- Design: .scratch/2026-09-17-plan-source-pages.md.

BEGIN;

CREATE TABLE IF NOT EXISTS source_pages (
    id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_url                  text NOT NULL CHECK (source_url <> ''),
    jurisdiction_ocdid          text NOT NULL REFERENCES jurisdictions(jurisdiction_ocdid),
    pipeline_run_id             uuid NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    -- Null for a run that never reached ingest.
    changeset_id                uuid REFERENCES changesets(id) ON DELETE CASCADE,
    organization_ids            uuid[] NOT NULL DEFAULT '{}',
    page_hash                   text,
    prompt_hash                 text,
    cache_path                  text,
    anchor_text                 text,
    is_relevant                 boolean,
    relevant_urls               text[],
    heuristics_failures         text[] NOT NULL DEFAULT '{}',
    -- The row where the LLM last actually read this page; null when it read it in this run.
    unchanged_since_source_page_id uuid REFERENCES source_pages(id) ON DELETE SET NULL,
    created_at                  timestamptz NOT NULL DEFAULT now(),
    UNIQUE (pipeline_run_id, source_url)
);

CREATE INDEX IF NOT EXISTS source_pages_source_url_created_at_idx
    ON source_pages (source_url, created_at DESC);
CREATE INDEX IF NOT EXISTS source_pages_jurisdiction_ocdid_idx
    ON source_pages (jurisdiction_ocdid);
CREATE INDEX IF NOT EXISTS source_pages_changeset_id_idx
    ON source_pages (changeset_id);

COMMIT;
