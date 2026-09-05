// The three buckets a state's section breaks into. Mirrors BUCKET_* in
// database/changeset_summaries.py — the API takes these as path values.

export const BUCKET_REVIEW = "review";
export const BUCKET_DISMISSED = "dismissed";
export const BUCKET_PUBLISHED = "published";

export const BUCKET_LABEL: Record<string, string> = {
  [BUCKET_REVIEW]: "To review",
  [BUCKET_DISMISSED]: "Dismissed",
  [BUCKET_PUBLISHED]: "Published",
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
