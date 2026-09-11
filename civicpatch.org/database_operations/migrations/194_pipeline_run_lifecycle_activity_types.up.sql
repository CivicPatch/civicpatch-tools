BEGIN;

-- A run beginning or settling, not a change to what the roster is — the home page's live
-- activity feed and /activity/changelogs pick these up automatically since both already read
-- every row in `activity` with no allowlist of types.
INSERT INTO activity_types (type) VALUES ('pipeline_run_start'), ('pipeline_run_end')
    ON CONFLICT (type) DO NOTHING;

COMMIT;
