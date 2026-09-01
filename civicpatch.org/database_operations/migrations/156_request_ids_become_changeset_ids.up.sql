-- The last two columns still saying `request`. Pure rename: nothing added, dropped or retyped.
--
-- 152 renamed the table and the two singular id columns that pointed at it, but these two are
-- plural arrays and were left behind — which is precisely how a half-rename survives. A survey
-- of the schema afterwards found only four names carrying the old noun, and only these two are
-- wrong: `issues.pull_request_url` is a genuine GitHub pull request and stays.
--
-- `requested_by_user_id` comes too, as `created_by_user_id`. It stays **nullable**, and the null
-- is load-bearing: 304/304 sheet imports and 85/95 scrapes name a user, and the ten that do not
-- are machine-triggered. "Created by nobody" is a fact about automation here, not missing data.
--
-- **Idempotency**: postgres has no `IF EXISTS` for `RENAME COLUMN`, so each is guarded on the
-- catalog. Explicit `IF` per name rather than a loop, matching 152.
BEGIN;

DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'issues'
                 AND column_name = 'request_ids') THEN
        ALTER TABLE issues RENAME COLUMN request_ids TO changeset_ids;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'review_session_entries'
                 AND column_name = 'request_ids') THEN
        ALTER TABLE review_session_entries RENAME COLUMN request_ids TO changeset_ids;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_schema = 'public' AND table_name = 'changesets'
                 AND column_name = 'requested_by_user_id') THEN
        ALTER TABLE changesets RENAME COLUMN requested_by_user_id TO created_by_user_id;
    END IF;
END $$;

COMMIT;
