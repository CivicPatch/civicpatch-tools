// needs_review_count, not buckets.to_review — the bucket breakdown is
// priority-exclusive (blocked wins), so it undercounts jurisdictions that
// are both blocked and have an open PR. needs_review_count doesn't.
export function getNeedsReviewCount(coverage) {
  return coverage?.needs_review_count ?? 0;
}
