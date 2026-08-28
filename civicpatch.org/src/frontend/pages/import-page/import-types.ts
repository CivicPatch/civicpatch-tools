// Shapes and status words the import page shares with the API. The string values mirror
// `database.request_batches.BatchStatus` and `shared.utils.statuses.RequestReviewStatus` — if
// either changes, this changes with it.

export const BATCH_RUNNING = "running";
export const BATCH_SUCCEEDED = "succeeded";
export const BATCH_FAILED = "failed";
export const BATCH_ABANDONED = "abandoned";

export const REVIEW_PENDING = "pending";
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
  jurisdictions_skipped: string[];
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

export type ReviewPerson = {
  id: string;
  name: string;
  label: string;
  image: string | null;
};

export type ReviewJurisdiction = {
  jurisdiction_ocdid: string;
  name: string;
  request_id: string;
  review_status: string;
  people: ReviewPerson[];
};

export type BatchReview = {
  batch_id: string;
  status: string;
  jurisdictions: ReviewJurisdiction[];
};

export type PublishResult = {
  jurisdiction_ocdid: string;
  published: boolean;
  error: string | null;
};
