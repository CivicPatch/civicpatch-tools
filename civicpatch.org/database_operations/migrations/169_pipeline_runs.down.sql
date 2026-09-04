-- Exactly reverses the up. The columns it copied from are still on `changesets` at this point —
-- they are dropped by a later migration — so nothing has to be copied back.

BEGIN;

DROP TABLE IF EXISTS pipeline_runs;

COMMIT;
