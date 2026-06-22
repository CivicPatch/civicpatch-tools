BEGIN;

-- Reverse 101: return every cutoff to the epoch seed (the post-100 state).

UPDATE state_configs
SET min_scraped_at = 'epoch'::timestamptz;

COMMIT;
