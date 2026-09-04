-- `merge_review` renamed to `publish_review`.
--
-- The name is a fossil: publishing a review used to *be* merging a GitHub PR, and the log was
-- written by the merge worker. Publishing is a database write now and the open-data commit is a
-- downstream mirror of it, so nothing merges. The history page rendered it as "Merged review",
-- describing a step that no longer happens.
--
-- `publish_review` rather than `approve_review`: it names what the system did, matches the
-- route (`POST /reviews/{id}/publish`), and cannot be read as approved-but-not-published.
--
-- `close_review` is deliberately left alone. It covers 294 rows of which exactly one is a
-- human rejecting: 245 superseded, 15 cancelled, 9 errored, 5 unchanged. Renaming it
-- `reject_review` would assert a decision nobody made. Splitting the human case out is a
-- separate change.

BEGIN;

INSERT INTO change_log_types (type) VALUES ('publish_review')
    ON CONFLICT (type) DO NOTHING;

UPDATE change_logs SET type = 'publish_review' WHERE type = 'merge_review';

DELETE FROM change_log_types WHERE type = 'merge_review';

COMMIT;
