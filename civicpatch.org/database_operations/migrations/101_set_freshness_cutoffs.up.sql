BEGIN;

-- Raise every state's freshness cutoff from the epoch seed (migration 100) to 3 months
-- before deploy: scrapes within the last ~3 months read fresh, older read stale.
--
-- Per the engine design the cutoff drives BOTH display (dashboard %, map colors) AND the
-- scrape candidate queue (get_stale_jurisdictions: scraped_at < cutoff). So this is the
-- deliberate "launch a re-scrape campaign" lever — jurisdictions last scraped >3 months ago
-- become stale and re-enter the queue (paced by the candidate batch cap, not all at once).
--
-- Absolute, not rolling: the date is frozen at deploy time, so progress stays monotonic until
-- an admin bumps it again. Guarded to the epoch seed so it never stomps a later admin value.

UPDATE state_configs
SET min_scraped_at = now() - interval '3 months'
WHERE min_scraped_at = 'epoch'::timestamptz;

COMMIT;
