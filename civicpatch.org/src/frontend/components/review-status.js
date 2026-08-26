// Mirrors shared/utils/statuses.py RequestReviewStatus.
//
// Derived server-side from published_at / dismissed_at, so "pending" means nobody has decided
// about this scrape yet. Distinct from `is_running`, which says whether the run itself
// finished, and from the action states in use-review-actions, which are client-side only.
export const REVIEW_STATUS = Object.freeze({
  PENDING: "pending",
  PUBLISHED: "published",
  DISMISSED: "dismissed",
});
