BEGIN;

-- Jurisdiction search, step 2 (plan: .scratch/2026-08-07-plan-jurisdiction-search.md).
-- Promotes parentage out of `data` into a real column, ordered most-specific-first:
--
--     Seattle city    -> {.../county:king/government, .../state:wa/government}
--     King County     -> {.../state:wa/government}
--     Albion city     -> {.../state:mi/government}   (no parent_ocdids recorded upstream)
--
-- Why a text[] rather than a join table: parentage is a DAG (a place can straddle two
-- counties), so an adjacency list with one parent does not fit; and open-data can name a
-- parent that is not synced, so a foreign key would reject the child row rather than
-- leave its trail short. GIN makes the reverse question — everything inside a county —
-- answerable off the same column.
--
-- Why the ocdids and not the resolved names: ocdids are stable, names are not. Resolving
-- names at read time means a renamed county is correct immediately, while the part that
-- made the read query complicated — unnesting JSONB, unioning the implied state row,
-- deduping — is computed once at sync.

ALTER TABLE jurisdictions
    ADD COLUMN IF NOT EXISTS parent_ocdids TEXT[] NOT NULL DEFAULT '{}';

UPDATE jurisdictions j SET parent_ocdids = coalesce((
    SELECT array_agg(parent_ocdid ORDER BY ord) FROM (
        SELECT parent.ocdid AS parent_ocdid, parent.ordinality AS ord
          FROM jsonb_array_elements_text(
                   coalesce(j.data->'parent_ocdids', '[]'::jsonb)
               ) WITH ORDINALITY AS parent(ocdid, ordinality)
        UNION ALL
        -- The state is always a parent but is not always recorded: county rows carry no
        -- parent_ocdids at all, and NC/TN carry none anywhere. Sorted last, skipped when
        -- already present, and never added to the state's own row.
        SELECT 'ocd-jurisdiction/country:us/state:' || j.state || '/government', 1000
         WHERE j.level <> 'state'
           AND NOT coalesce(j.data->'parent_ocdids', '[]'::jsonb)
                   ? ('ocd-jurisdiction/country:us/state:' || j.state || '/government')
    ) all_parents
), '{}');

-- Answers "everything inside this county/state" from the same column the display uses.
CREATE INDEX IF NOT EXISTS jurisdictions_parent_ocdids_idx
ON jurisdictions USING GIN (parent_ocdids);

COMMIT;
