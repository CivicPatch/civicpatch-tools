BEGIN;

-- What a human asserted about a row: that it is right, that it should be something else, or
-- that an earlier assertion was wrong.
--
-- Replaces two designs that were never built — `field_overrides` (corrections) and
-- `verifications` (confirmations). Strip both to their columns and they are identical: an
-- entity, which part of it, who, when, on what basis. They differ by whether a replacement
-- value comes along. Two tables differing by one nullable column is the thing worth
-- collapsing, or every question about human input has to be asked twice and unioned.
--
-- APPEND-ONLY. No updates, no deletes. Verification needs history, which is why this is a
-- table rather than a `verified_at` column, and history is only trustworthy if rows never
-- change. Current state is derived: the latest row per (entity, field).
--
-- Distinct from `change_logs`, which is an audit trail — *what happened*. This is *what a
-- human asserts is true*. An audit log records that someone edited a field; it does not
-- record that someone checked a field and found it already correct.
CREATE TABLE assertions (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- No FK: the subjects are heterogeneous, which is the standard price of an event log.
    -- Bounded by refusing deletes rather than cleaning up after them — a post someone vouched
    -- for is history, the same way a post someone held is.
    entity_type  text NOT NULL,
    entity_id    uuid NOT NULL,

    -- NULL = the entity itself, not one of its fields. "This office exists" is not a field
    -- assertion. Postgres 15+ `NULLS NOT DISTINCT` below makes NULL behave in the constraint,
    -- so this needs no '*' sentinel — one column carrying two meanings is the mistake already
    -- corrected in `posts.status` and `PipelineRunStatus`.
    field_path   text,

    kind         text NOT NULL,

    -- Corrections only. NULL is already spoken for: it means "deliberately empty" — a human
    -- asserting the clerk has no email — which is why `kind` is needed and `value IS NULL`
    -- cannot stand in for it.
    value        jsonb,

    -- [{note, url}] — the shape `openstates/people` defines. `note` may stand alone: the
    -- reason this could not be a column is "phoned the clerk, there really are five trustees",
    -- evidence that exists nowhere else because it came from outside a publish.
    sources      jsonb,

    -- NOT NULL, unlike `requests.resolved_by_user_id` where NULL means a machine gave up.
    -- An assertion nobody made is not an assertion.
    asserted_by  uuid NOT NULL REFERENCES users(id),
    asserted_at  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT assertions_entity_type_check
        CHECK (entity_type IN ('post', 'membership', 'person')),
    CONSTRAINT assertions_kind_check
        CHECK (kind IN ('confirm', 'correct', 'retract')),
    -- A correction with no value is indistinguishable from a confirmation.
    CONSTRAINT assertions_correct_has_value
        CHECK (kind <> 'correct' OR value IS NOT NULL OR field_path IS NOT NULL),

    CONSTRAINT assertions_no_exact_duplicate
        UNIQUE NULLS NOT DISTINCT (entity_type, entity_id, field_path, asserted_by, asserted_at)
);

-- "What is the latest assertion about this row" — the shape every read takes.
CREATE INDEX assertions_entity_idx
    ON assertions (entity_type, entity_id, asserted_at DESC);

COMMIT;
