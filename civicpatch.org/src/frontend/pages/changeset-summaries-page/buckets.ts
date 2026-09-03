// The three buckets a state's section breaks into. Mirrors BUCKET_* in
// database/changeset_summaries.py — the API takes these as path values.

export const BUCKET_REVIEW = "review";
export const BUCKET_FAILED = "failed";
export const BUCKET_OK = "ok";

export const BUCKET_LABEL: Record<string, string> = {
  [BUCKET_REVIEW]: "To review",
  [BUCKET_FAILED]: "Failed",
  [BUCKET_OK]: "Ok",
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
