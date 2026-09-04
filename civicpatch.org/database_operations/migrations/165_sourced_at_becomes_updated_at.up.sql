-- `changesets.sourced_at` becomes `updated_at`, because that is what it holds.
--
-- The name claims a source was read. On **314 of 414 rows it was not**: every `sheet_import`
-- and every `people_edit` carries a value, and on all of them it is byte-identical to
-- `created_at`. Only the 100 scrapes have a real gap, and 90 of those differ — by up to two
-- days.
--
-- It overclaims on scrapes too. `update_pipeline_run_status` writes CURRENT_TIMESTAMP on every
-- report, including a bare progress ping, so it is *our* clock at the last check-in rather than
-- the moment a source was read. Replay an artifact from last month and it becomes today.
--
-- What the column means across all three kinds is "when this changeset's content last moved" —
-- which is `updated_at`, and is exactly what `supersede_stacked_requests` orders on: which
-- changeset is freshest.
--
-- ⚠️ 147 REMOVED an `updated_at` here, and this is not a regression of that decision. It
-- argued: "every event on a request already has its own timestamp — `created_at` for the ask,
-- `published_at` and `dismissed_at` for the decision — so a generic `updated_at` had nothing
-- left to mean, and no writer." True of *that* column. This one has a writer (every pipeline
-- report) and a meaning (content freshness), and four other tables already spell it this way.
--
-- The index follows the column; `idx_changesets_pending_by_jurisdiction` names neither.

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'public'
           AND table_name = 'changesets'
           AND column_name = 'sourced_at'
    ) THEN
        ALTER TABLE changesets RENAME COLUMN sourced_at TO updated_at;
    END IF;
END $$;

COMMIT;
