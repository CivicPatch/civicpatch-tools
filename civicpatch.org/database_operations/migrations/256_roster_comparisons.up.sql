-- A roster from outside (an agent's upload of a state's officials) compared with civicpatch's,
-- kept forever so a state's numbers can be followed across runs. Read-only towards everything
-- else: nothing here is a fact, a claim or a changeset.
--
-- person_id has no FK: a run records what civicpatch held then, and must survive that person
-- being deleted later.

BEGIN;

CREATE TABLE IF NOT EXISTS roster_comparison_runs (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    state                   text NOT NULL,
    started_by_user_id      uuid NOT NULL REFERENCES users(id),
    started_at              timestamptz NOT NULL DEFAULT now(),
    source_columns          jsonb NOT NULL,
    corrections             jsonb NOT NULL,
    rates                   jsonb NOT NULL,
    jurisdictions_not_named integer NOT NULL
);

CREATE INDEX IF NOT EXISTS roster_comparison_runs_state_started_at_idx
    ON roster_comparison_runs (state, started_at DESC);

CREATE TABLE IF NOT EXISTS roster_comparison_jurisdictions (
    run_id             uuid NOT NULL REFERENCES roster_comparison_runs(id) ON DELETE CASCADE,
    jurisdiction_ocdid text NOT NULL,
    rates              jsonb NOT NULL,
    PRIMARY KEY (run_id, jurisdiction_ocdid)
);

CREATE TABLE IF NOT EXISTS roster_comparison_people (
    run_id             uuid NOT NULL REFERENCES roster_comparison_runs(id) ON DELETE CASCADE,
    jurisdiction_ocdid text NOT NULL,
    position           integer NOT NULL,
    outcome            text NOT NULL,
    source_row         integer,
    person_id          uuid,
    comparison         jsonb NOT NULL,
    PRIMARY KEY (run_id, jurisdiction_ocdid, position)
);

ALTER TABLE roster_comparison_people DROP CONSTRAINT IF EXISTS roster_comparison_people_outcome_check;
ALTER TABLE roster_comparison_people ADD CONSTRAINT roster_comparison_people_outcome_check CHECK (
    outcome IN ('matched', 'possible_match', 'only_in_uploaded_data', 'only_in_civicpatch')
);

COMMIT;
