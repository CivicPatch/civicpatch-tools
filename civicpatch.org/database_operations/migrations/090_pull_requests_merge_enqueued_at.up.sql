BEGIN;

-- Tracks when a merge was enqueued for a PR. Owned solely by the in-app merge flow
-- (set at enqueue, cleared when the merge settles); the GitHub sync never touches it.
-- Lets "available for review" exclude in-flight merges without overloading `status`,
-- which the sync reconciles to GitHub's view. The timestamp self-heals: a stuck/lost
-- merge falls back into the available pool once the window elapses.
ALTER TABLE pull_requests ADD COLUMN IF NOT EXISTS merge_enqueued_at TIMESTAMPTZ;

COMMIT;
