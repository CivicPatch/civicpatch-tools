-- Publish state moves from `pull_requests` onto `requests`.
--
-- `pull_requests.request_id` is UNIQUE, so that table is strictly 1:1 with `requests`. For a
-- scrape, every column in it is really a request column that was side-tabled because the
-- state lived on GitHub. Now that civicpatch publishes to the database directly, "has this
-- been published / dismissed, by whom, and where did it land" are properties of the request.
--
-- The table itself stays: jurisdiction-edit requests still open real pull requests, and the
-- historical scrape rows are kept rather than deleted.
--
-- Four columns replace six:
--   published_at   <- status='merged' + merged_at + merge_enqueued_at (publishing parked the
--                     PR by setting merge_enqueued_at, so either meant "the reviewer acted")
--   dismissed_at    <- status='closed'
--   resolved_by_user_id <- same name, same meaning: whoever published or dismissed it
--   open_data_url  <- url. Deliberately not `commit_url`: backfilled rows hold a pull request
--                     URL and new rows will hold a commit URL. The column answers "where did
--                     this land in open-data", which is true of both.
--
-- Backfill caveat, measured 2026-08-16: only 3 of 41 merged rows carry `merged_at` and none
-- carry `merge_enqueued_at`, so `updated_at` is the fallback — the row's last write was the
-- merge. Approximate for historical rows; exact for everything published from here on.
--
-- Idempotent: columns are added IF NOT EXISTS, and the backfill only touches rows still NULL.
BEGIN;

ALTER TABLE requests ADD COLUMN IF NOT EXISTS published_at timestamptz;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS dismissed_at timestamptz;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS resolved_by_user_id uuid;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS open_data_url text;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'requests_resolved_by_user_id_fkey'
    ) THEN
        ALTER TABLE requests
            ADD CONSTRAINT requests_resolved_by_user_id_fkey
            FOREIGN KEY (resolved_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
END $$;

UPDATE requests r
   SET published_at = COALESCE(pr.merged_at, pr.merge_enqueued_at, pr.updated_at)
  FROM pull_requests pr
 WHERE pr.request_id = r.id
   AND r.published_at IS NULL
   AND (pr.status = 'merged' OR pr.merge_enqueued_at IS NOT NULL);

UPDATE requests r
   SET dismissed_at = pr.updated_at
  FROM pull_requests pr
 WHERE pr.request_id = r.id
   AND r.dismissed_at IS NULL
   AND pr.status = 'closed';

UPDATE requests r
   SET resolved_by_user_id = pr.resolved_by_user_id,
       open_data_url = pr.url
  FROM pull_requests pr
 WHERE pr.request_id = r.id
   AND r.resolved_by_user_id IS NULL
   AND r.open_data_url IS NULL;

-- A request cannot be both published and dismissed. Nothing enforced this when the state was
-- a single `status` string, because the two were spellings of one column; split apart, they
-- need the constraint back.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'requests_publish_state_check'
    ) THEN
        ALTER TABLE requests
            ADD CONSTRAINT requests_publish_state_check
            CHECK (published_at IS NULL OR dismissed_at IS NULL);
    END IF;
END $$;

COMMIT;
