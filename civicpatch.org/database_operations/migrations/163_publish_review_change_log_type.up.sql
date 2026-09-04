-- The two ways a review ends get real names: `merge_review` → `publish_review`,
-- `close_review` → `dismiss_review`.
--
-- Both were fossils, for different reasons.
--
-- `merge_review` described the mechanism: publishing a review used to *be* merging a GitHub PR,
-- and the log was written by the merge worker. Publishing is a database write now and the
-- open-data commit is a downstream mirror of it, so nothing merges. The history page rendered
-- it as "Merged review", describing a step that no longer happens.
--
-- `close_review` borrowed a word that already means something else here. Counted across `src/`,
-- `close` belongs to seats — `memberships.closed_at` (32 uses), `closed` (13) — while every
-- other name on the review path says dismiss: `dismissed_at`, `dismissed_reason`,
-- `dismiss_request`, `mark_dismissed`, `dismiss_superseded_by`. So it was a dismissal wearing
-- the wrong word.
--
-- `publish_review` rather than `approve_review`: it names what the system did, matches the
-- route (`POST /reviews/{id}/publish`), and cannot be read as approved-but-not-published.
--
-- `dismiss_review` rather than `reject_review`: the type covers 294 rows of which exactly one
-- is a human rejecting — 245 superseded, 15 cancelled, 9 errored, 5 unchanged. `reject` would
-- assert a decision nobody made, and it is already taken twice over (`DismissalReason.REJECTED`
-- is one of five reasons, and `AssertionKind.REJECT` is a different domain entirely).
--
-- No behaviour change: the logs' payloads, readers and filters are untouched.

BEGIN;

INSERT INTO change_log_types (type) VALUES ('publish_review'), ('dismiss_review')
    ON CONFLICT (type) DO NOTHING;

UPDATE change_logs SET type = 'publish_review' WHERE type = 'merge_review';
UPDATE change_logs SET type = 'dismiss_review' WHERE type = 'close_review';

DELETE FROM change_log_types WHERE type IN ('merge_review', 'close_review');

COMMIT;
