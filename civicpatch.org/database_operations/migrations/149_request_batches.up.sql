-- One run of something that produced many requests at once, and the link from each request
-- back to it.
--
-- **Not sheet-specific on purpose.** A curated-sheet import makes N requests; so does a state
-- scrape run — `get_scrape_candidates(state, n)` already returns N jurisdictions and produces N
-- review cards, it just has no record that they belong together. #2463 (re-scrape Washington)
-- and #2424 (Scrape Maine) are both batches today with nothing naming them.
--
-- Distinct from `requests`, which 147 made "the ask" about **one** jurisdiction. That merge
-- collapsed a genuine 1:1 — `pipeline_runs.request_id` was UNIQUE NOT NULL, 82/82/0 on dev.
-- This is 1:N, which is a different relationship and not a vertical partition.
--
-- **A batch's items are its requests.** There is no `result` blob and no items table: everything
-- a finished item did is already answerable — `source_records` by `request_id` for sightings,
-- `source_record_identities` for people, `change_logs` of type `add_post` for seats. Storing a
-- copy is the mistake 140 corrected on `source_records.parsed` and 148 on `posts.label`.
--
-- What that gives up: an item that produced *nothing* — skipped because nobody ticked it ready,
-- or failed before a request existed — leaves no row here. It is reported in the run's response
-- and written into the volunteer's own sheet, which is the durable record for the person who
-- needs it.
--
-- `status` is the lifecycle only. Progress is `count(requests WHERE batch_id = …)` against
-- `items_total`, which is set to the number of items the run will actually attempt. 147 has just
-- finished unpicking `pipeline_runs.status` carrying two axes; a new table does not reintroduce
-- the shape.
--
-- `lock_key` rather than a spreadsheet id: "do not run two of these over the same thing" is not
-- sheet-shaped. `sheet:<id>` for an import, `state:wa` for a scrape run.
BEGIN;

CREATE TABLE IF NOT EXISTS request_batches (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    kind                 text NOT NULL,
    -- What this run must not race. Held for the run's lifetime by the partial index below.
    lock_key             text NOT NULL,
    -- Producer-specific inputs: the spreadsheet, or the state and how many towns.
    arguments_json       jsonb NOT NULL DEFAULT '{}'::jsonb,

    status               text NOT NULL DEFAULT 'running',
    -- How many items the run will attempt. The denominator; the numerator is a count of the
    -- requests it has made so far.
    items_total          integer,

    error                text,

    started_by_user_id   uuid NOT NULL REFERENCES users (id),
    started_at           timestamptz NOT NULL DEFAULT now(),
    finished_at          timestamptz,

    CONSTRAINT request_batches_kind_check
        CHECK (kind IN ('sheet_import', 'state_scrape')),
    CONSTRAINT request_batches_status_check
        CHECK (status IN ('running', 'succeeded', 'failed', 'abandoned'))
);

-- The lock, enforced rather than agreed: one running batch per target. A crashed run holds it
-- until a person clears it — deliberate, because a timeout cannot tell a dead run from a slow
-- one, and stealing from a live one is worse than waiting.
CREATE UNIQUE INDEX IF NOT EXISTS request_batches_one_running_per_key
    ON request_batches (lock_key) WHERE finished_at IS NULL;

-- "What has this target done lately", newest first.
CREATE INDEX IF NOT EXISTS request_batches_key_started_idx
    ON request_batches (lock_key, started_at DESC);

-- The link, on the many side where the cardinality puts it: one batch makes many requests. It
-- is also the progress count and the bulk review screen's whole query, which is why it is a
-- column with an index rather than a probe into jsonb. NULL for every request made outside a
-- batch, which is most of them.
ALTER TABLE requests ADD COLUMN IF NOT EXISTS batch_id uuid REFERENCES request_batches (id);

CREATE INDEX IF NOT EXISTS idx_requests_batch_id ON requests (batch_id);

COMMIT;
