-- A withdrawal is a withdraw row (214); the columns written alongside it go. Readers ask
-- claim_is_live instead, which follows withdraws of withdraws the way the fold does.

BEGIN;

-- The database's copy of core/projection/live_facts.py for claims; the two must agree.
CREATE OR REPLACE FUNCTION claim_is_live(claim_id uuid)
RETURNS boolean LANGUAGE plpgsql STABLE AS $$
BEGIN
    RETURN NOT EXISTS (
        SELECT 1 FROM claims w
         WHERE w.entity_type = 'claim' AND w.entity_id = claim_id AND w.kind = 'withdraw'
           AND claim_is_live(w.id)
    );
END
$$;

ALTER TABLE claims DROP CONSTRAINT IF EXISTS claims_withdrawn_together;
ALTER TABLE claims
    DROP COLUMN IF EXISTS withdrawn_at,
    DROP COLUMN IF EXISTS withdrawn_by,
    DROP COLUMN IF EXISTS withdrawn_reason,
    DROP COLUMN IF EXISTS withdrawn_by_changeset_id;

COMMIT;
