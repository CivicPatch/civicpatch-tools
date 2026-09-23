BEGIN;

-- `load_facts` reads a jurisdiction's withdraws on every fold, and `assertions` has no index
-- on `kind`, so the predicate seq-scans the table. Partial, because only withdraws are read
-- this way and they are a small fraction of the rows.
CREATE INDEX IF NOT EXISTS assertions_withdraw_changeset_idx
    ON assertions (changeset_id)
    WHERE kind = 'withdraw';

COMMIT;
