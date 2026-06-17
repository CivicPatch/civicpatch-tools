BEGIN;

-- Reverse 100. Dropping scraped_at drops jurisdictions_state_scraped_at_idx with it.

DROP TABLE synced_files;
DROP TABLE state_configs;

ALTER TABLE jurisdictions DROP COLUMN scraped_at;

COMMIT;
