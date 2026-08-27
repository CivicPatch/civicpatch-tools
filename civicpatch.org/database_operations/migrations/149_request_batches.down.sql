-- The column goes before the table it references, or the foreign key blocks the drop.
--
-- Lossy, and honestly so: the batch records go, and with them the only account of items that
-- were skipped or failed — those never had a request to survive in. The requests a batch made
-- survive, they just stop knowing they were made together.
BEGIN;

DROP INDEX IF EXISTS idx_requests_batch_id;
ALTER TABLE requests DROP COLUMN IF EXISTS batch_id;

DROP TABLE IF EXISTS request_batches;

COMMIT;
