-- The stored country config predates 253's member merge and gives two roles the `member` alias,
-- which ConfigFile now rejects; every read and the sync's own diff fail on it. Re-sync after deploy.

BEGIN;

DELETE FROM jurisdiction_configs WHERE path = 'data_source/config.yml';

COMMIT;
