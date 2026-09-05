-- What every LLM call cost, one row per HTTP call.
--
-- The cost is what the provider charged: OpenRouter states it in `usage.cost` when the request
-- asks for it. It is never computed here. The price table this replaces
-- (`pipelines/src/utils/cost_utils.py::llm_model_prices`) fell through to zero for any
-- (model, provider) pair nobody had listed, so a model bump reported free work rather than
-- failing.
--
-- Grain is the HTTP call, not the page: `prompt_name`, `source_url` and `chunk_index` describe
-- what a call read, they do not identify it.
--
-- The cache folder holding the `preprocessed.md` the model saw is NOT stored: it is
-- `format_url_to_folder(source_url)`, a pure function of a column already here. Store it only if
-- that slug function ever changes, which would make old rows underivable. The two retry loops are separate columns because they mean
-- different things — `attempt` is the transport retry inside one call, `seed` marks the
-- heuristics pass that re-ran the whole prompt.
--
-- Every row is a call that reached us with a 2xx and was billed. `error` says whether we got
-- anything for it: NULL if we used the response, otherwise why we could not. Those failures were
-- invisible before 2026-09-04, including a 734-second repetition loop retried five times over.
--
-- Grounded Google calls are deliberately absent: their API states no cost, and a zero would
-- read as free.

BEGIN;

CREATE TABLE IF NOT EXISTS llm_calls (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_run_id     uuid NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    -- Which prompt, not which step: steps get renamed and split (04a exists because of one),
    -- and rows are history. The prompt is the thing whose cost this measures, and it is the key
    -- the evals are already organised by.
    prompt_name         text NOT NULL,
    -- what it read
    source_url          text,
    chunk_index         smallint,
    chunk_count         smallint,
    attempt             smallint NOT NULL DEFAULT 1,
    seed                smallint,
    -- who answered, and by what route
    gateway             text NOT NULL,
    model               text NOT NULL,
    routed_model        text NOT NULL,
    upstream_provider   text NOT NULL,
    generation_id       text,
    input_tokens        integer NOT NULL,
    output_tokens       integer NOT NULL,
    cached_input_tokens integer NOT NULL DEFAULT 0,
    reasoning_tokens    integer NOT NULL DEFAULT 0,
    -- Charged, never computed. Unconstrained on purpose: a provider that bills oddly should
    -- show up in the data, not fail the write.
    cost_usd            numeric NOT NULL,
    web_search          boolean NOT NULL DEFAULT false,
    duration_ms         integer,
    -- how it ended
    -- `finish_reason` is OpenRouter's, verbatim: 'stop' | 'length' | 'content_filter'.
    -- 'length' means WE truncated it at _MAX_OUTPUT_TOKENS, which is a config fix, not a model
    -- problem — and the JSON comes back cut mid-structure, so it bills in full and parses never.
    finish_reason       text,
    -- Ours, and the only verdict column: NULL means we used the response, otherwise why not.
    -- One column rather than a boolean beside it, so there is no state where the two disagree.
    -- Never a transport error: every row here is a 2xx that billed.
    error               text,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- Every read is "this run's calls".
CREATE INDEX IF NOT EXISTS llm_calls_run_idx ON llm_calls (pipeline_run_id);

COMMIT;
