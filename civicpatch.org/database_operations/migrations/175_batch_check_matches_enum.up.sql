-- `changeset_batches`'s two CHECKs disagreed with the enums they copy.
--
-- Found 2026-09-05 by `test_check_constraints_match_enums.py` on its first run.
--
-- 1. `kind` allowed 'scrape'; `BatchKind.STATE_SCRAPE` is 'state_scrape'. Not cosmetic — the
--    first attempt to open a scrape batch would have raised a CheckViolation. Nothing has ever
--    opened one (34 rows, all sheet_import), so there is nothing to migrate and the enum's
--    spelling wins: a batch covers a whole state, which is what the name says.
--
-- 2. `status` allowed 'abandoned', which `BatchStatus` does not define — the column could hold
--    a value Python could not parse back. Nothing writes it. Removed rather than added to the
--    enum: an unreachable state is better re-introduced when something needs it than carried
--    as a value with no writer.

BEGIN;

ALTER TABLE changeset_batches DROP CONSTRAINT IF EXISTS changeset_batches_kind_check;
ALTER TABLE changeset_batches ADD CONSTRAINT changeset_batches_kind_check
    CHECK (kind = ANY (ARRAY['sheet_import'::text, 'state_scrape'::text]));

ALTER TABLE changeset_batches DROP CONSTRAINT IF EXISTS changeset_batches_status_check;
ALTER TABLE changeset_batches ADD CONSTRAINT changeset_batches_status_check
    CHECK (status = ANY (ARRAY['running'::text, 'succeeded'::text, 'failed'::text]));

COMMIT;
