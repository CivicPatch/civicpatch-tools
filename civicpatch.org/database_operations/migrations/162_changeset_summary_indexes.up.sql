-- The three indexes the cross-state rollup needs. Each was measured, none guessed: the numbers
-- come from a throwaway database built to production shape (9,524 jurisdictions with a 25 MB
-- heap, 47,620 changesets, 64,368 change_logs), committed and VACUUM ANALYZEd. Benchmarking
-- inside an uncommitted transaction reports nonsense — 240k uncommitted rows mean no visibility
-- map, so index-only scans degrade to heap fetches.

BEGIN;

-- Both queue CTEs join `jurisdictions` only to map ocdid -> state, but the table's heap is
-- 25 MB because of the `data` jsonb. Carrying `state` in the index makes that an index-only
-- scan. 275 ms -> 99 ms, the single largest win in the query.
CREATE INDEX IF NOT EXISTS idx_jurisdictions_ocdid_state
    ON jurisdictions (jurisdiction_ocdid, state);

-- The queue is deliberately unwindowed, so without this its scan is O(table) forever. Partial
-- on the two NULLs bounds it by how many changesets are *pending* — 22,392 in the benchmark,
-- and at most one per jurisdiction once `DISTINCT ON` has run. 205 ms -> 96 ms, and flat as
-- history grows: 1.7 ms at 571k changesets and 1.7 ms at 1.62M.
--
-- `sourced_at DESC` is in the key, not just the predicate: `valid_queue` takes
-- `DISTINCT ON (jurisdiction_ocdid) ... ORDER BY jurisdiction_ocdid, sourced_at DESC`, so the
-- index serves the dedup ordering as well as the filter.
CREATE INDEX IF NOT EXISTS idx_changesets_pending_by_jurisdiction
    ON changesets (jurisdiction_ocdid, sourced_at DESC)
    WHERE published_at IS NULL AND dismissed_at IS NULL;

-- For the windowed flows scan. Worth stating plainly because it looks useless today and is not:
-- at 38k changesets a 30-day window covers 99% of the table, so the planner correctly ignores
-- this. At 1.6M rows the same window is 2.4% and it becomes essential — 77 ms -> 15 ms. An
-- index measured on a small table can be the wrong answer for a big one.
CREATE INDEX IF NOT EXISTS idx_changesets_created_at
    ON changesets (created_at DESC);

COMMIT;
