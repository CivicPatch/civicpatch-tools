// Shapes and status words the import page shares with the API. The string values mirror
// `database.request_batches.BatchStatus` and `shared.utils.statuses.RequestReviewStatus` — if
// either changes, this changes with it.

export const BATCH_RUNNING = "running";
export const BATCH_SUCCEEDED = "succeeded";
export const BATCH_FAILED = "failed";

// Mirrors `ChangesetState.OPEN`. Not "pending" — `issues.status` means something else by
// that word, and an open changeset with pending issues is a thing we say often.
export const CHANGESET_OPEN = "open";
export const REVIEW_PUBLISHED = "published";

export function isFinished(status: string): boolean {
  return status !== BATCH_RUNNING;
}

export type RowError = {
  line: number;
  jurisdiction_ocdid: string;
  column: string | null;
  message: string;
};

export type ImportPreview = {
  jurisdictions_ready: string[];
  jurisdictions_blocked: string[];
  rows: number;
  errors: RowError[];
};

export type ImportProgress = {
  batch_id: string;
  status: string;
  items_total: number | null;
  items_done: number;
  error: string | null;
  started_at: string;
  finished_at: string | null;
};

// Mirrors core/roster_diff.py: ChangeCounts.
export type ChangeCounts = {
  added_people: number;
  changed_people: number;
  absent_memberships: number;
};

export type ReviewJurisdiction = {
  jurisdiction_ocdid: string;
  name: string;
  changeset_id: string;
  changeset_state: string;
  people: number;
  change_counts: ChangeCounts;
};

export type BatchReview = {
  batch_id: string;
  status: string;
  jurisdictions: ReviewJurisdiction[];
};

export type PublishResult = {
  changeset_id: string;
  jurisdiction_ocdid: string;
  published: boolean;
  error: string | null;
};
