// The four buckets a state's section breaks into. Mirrors BUCKET_* in
// database/changeset_summaries.py — the API takes these as path values.

export const BUCKET_REVIEW = "review";
export const BUCKET_DISMISSED = "dismissed";
export const BUCKET_PUBLISHED = "published";
// Read from `pipeline_runs`, not `changesets`: attempts that proposed nothing, so no changeset
// exists for the other three to have found.
export const BUCKET_FAILED_RUNS = "failed_runs";

export const BUCKET_LABEL: Record<string, string> = {
  [BUCKET_REVIEW]: "To review",
  [BUCKET_DISMISSED]: "Dismissed",
  [BUCKET_PUBLISHED]: "Published",
  [BUCKET_FAILED_RUNS]: "Failed",
};

export interface BucketRow {
  jurisdiction_ocdid: string;
  jurisdiction_path: string;
  name: string | null;
  days_waiting: number | null;
  failure_reason: string | null;
}

export interface BucketPage {
  total: number;
  rows: BucketRow[];
}
