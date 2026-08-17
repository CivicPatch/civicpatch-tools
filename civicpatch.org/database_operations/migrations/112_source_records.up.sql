-- source_records: append-only evidence, one row per person per scrape.
--
-- Nothing today holds (role, division, label). `people.data` holds a rendered `Official`
-- whose `office.name` is one string, so the derivation cannot be replayed, audited, or
-- diffed. This is the table 2.5 derives posts/memberships from.
--
-- Both halves are stored because every step is lossy: parse (raw label -> role + division +
-- unmatched), usurp (N roles -> 1) and render (structured -> one office.name) each discard
-- something. Keeping only the input is not enough — re-running a fixed parser yields today's
-- answer, not the one that was published, and review is the gate, so what a reviewer
-- approved is itself an audit fact.
--
--   raw     the Record as it arrived, labels verbatim  — truth for re-derivation
--   parsed  the structured decision that was published — historical by construction
--
-- Write-once, both halves. A replayed parser fix writes posts/memberships and may add a new
-- row; it must never rewrite an existing `parsed`, which would destroy the fact the row
-- exists to hold. Current state lives in `people` and (from 113) posts/memberships — never
-- read `parsed` as current.
--
-- NO UNIQUE CONSTRAINT, deliberately. "One row per person per scrape" is a writer invariant,
-- not a table constraint: unique(request_id, person_id) would forbid exactly the replay the
-- design calls for. The uuid pk is the identity, and `created_at` orders derivations. If
-- duplicate evidence proves real, the fix is an idempotent writer keyed on request_id; a
-- partial unique index can be added later without rewriting the table.
--
-- NOT PARTITIONED. ~30 MB per full pass against a 28 MB largest-table database, and no
-- partitioned tables exist in this schema today. Revisit when it is genuinely large.
-- Idempotent: guarded on the table not already existing.
BEGIN;

DO $$
BEGIN
    IF to_regclass('public.source_records') IS NULL THEN
        CREATE TABLE source_records (
            id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            request_id         uuid NOT NULL REFERENCES requests (id) ON DELETE CASCADE,
            -- The Record id, which is also the membership FK. Text, not uuid: it is the
            -- pipeline's person id (#2472 measured its churn across re-scrapes).
            person_id          text NOT NULL,
            jurisdiction_ocdid text NOT NULL REFERENCES jurisdictions (jurisdiction_ocdid),
            raw                jsonb NOT NULL,
            parsed             jsonb NOT NULL,
            -- NULL until the triple is materialised. Publication is an event, not an
            -- inference.
            published_at       timestamptz,
            created_at         timestamptz NOT NULL DEFAULT now()
        );

        -- What did this scrape derive.
        CREATE INDEX source_records_request_id_idx ON source_records (request_id);
        -- One person's history, newest first — the replay and blast-radius pairing.
        CREATE INDEX source_records_person_id_created_at_idx
            ON source_records (person_id, created_at DESC);
        -- Per-jurisdiction triage; the orphan gate applies here as elsewhere.
        CREATE INDEX source_records_jurisdiction_ocdid_idx
            ON source_records (jurisdiction_ocdid);
        -- The candidate feed: unresolved labels are read out of `parsed` rather than
        -- collected separately, so containment queries over it are the mechanism, not an
        -- optimisation.
        CREATE INDEX source_records_parsed_idx
            ON source_records USING gin (parsed jsonb_path_ops);
    END IF;
END $$;

COMMIT;
