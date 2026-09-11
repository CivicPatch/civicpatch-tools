BEGIN;

-- A curated sheet's rows landing in the review queue, same live-feed treatment as
-- pipeline_run_start/end (194) — the home page's activity widget and /activity/changelogs
-- pick it up automatically.
INSERT INTO activity_types (type) VALUES ('sheet_import')
    ON CONFLICT (type) DO NOTHING;

COMMIT;
