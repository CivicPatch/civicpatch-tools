-- `assertions.asserted_at` becomes `created_at`, and `asserted_by` becomes `created_by`. Pure
-- renames: no column added, dropped or retyped, and no values change.
--
-- The table is insert-only (187) — a row is never updated except to stamp/clear its withdrawal
-- columns, never to change when it was asserted or who asserted it — so there is no separate
-- "created" moment or "created by" person to distinguish from "asserted". Both names matched
-- every other table in this schema (`changesets`, `activity`, `people`, ...) only after this;
-- `asserted_at`/`asserted_by` just said the same thing with an extra word, since the table's
-- own name already says every row in it is an assertion. `created_by` alongside `withdrawn_by`
-- is also a cleaner, more parallel pair than `asserted_by`/`withdrawn_by`.
--
-- `withdrawn_at`/`withdrawn_by` are NOT touched: they name a real, later, distinct event — an
-- UPDATE, not the INSERT — so a generic name would lose information these don't.
--
-- `created_at`'s index (`assertions_entity_idx`) carries no `asserted_at` substring, so nothing
-- there needs a parallel rename — postgres updates an index's own column reference
-- automatically when the underlying column is renamed. `created_by`'s FK constraint is NOT
-- index-backed, so it does need its own rename, same reasoning 152/190 already applied to
-- their own renamed columns.
--
-- **Idempotency**: postgres has no `IF EXISTS` for `RENAME COLUMN` or `RENAME CONSTRAINT`, so
-- both are guarded on the catalog, same idiom as 152/190.
BEGIN;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'assertions'
                 AND column_name = 'asserted_at') THEN
        ALTER TABLE assertions RENAME COLUMN asserted_at TO created_at;
    END IF;
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'assertions'
                 AND column_name = 'asserted_by') THEN
        ALTER TABLE assertions RENAME COLUMN asserted_by TO created_by;
    END IF;
END $$;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'assertions_asserted_by_fkey') THEN
        ALTER TABLE assertions RENAME CONSTRAINT assertions_asserted_by_fkey
            TO assertions_created_by_fkey;
    END IF;
END $$;

COMMIT;
