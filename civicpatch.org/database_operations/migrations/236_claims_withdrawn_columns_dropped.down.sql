-- Reverses 236's schema. The columns come back empty: the withdraw rows still hold every withdrawal.

BEGIN;

ALTER TABLE claims
    ADD COLUMN IF NOT EXISTS withdrawn_at timestamptz,
    ADD COLUMN IF NOT EXISTS withdrawn_by uuid REFERENCES users(id),
    ADD COLUMN IF NOT EXISTS withdrawn_reason text,
    ADD COLUMN IF NOT EXISTS withdrawn_by_changeset_id uuid REFERENCES changesets(id) ON DELETE SET NULL;

ALTER TABLE claims DROP CONSTRAINT IF EXISTS claims_withdrawn_together;
ALTER TABLE claims ADD CONSTRAINT claims_withdrawn_together
    CHECK ((withdrawn_at IS NULL) = (withdrawn_by IS NULL));

CREATE INDEX IF NOT EXISTS claims_withdrawn_by_changeset_id_idx ON claims (withdrawn_by_changeset_id);

DROP FUNCTION IF EXISTS claim_is_live(uuid);

COMMIT;
