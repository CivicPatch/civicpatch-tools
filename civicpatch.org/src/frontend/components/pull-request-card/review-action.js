// What a reviewer's action is doing to a card, client-side only. Not a status the server
// holds — that is `RequestReviewStatus`, derived from published_at/dismissed_at.
export const REVIEW_ACTION = {
  APPROVING: "approving",
  APPROVED: "approved",
  REJECTING: "rejecting",
  REJECTED: "rejected",
  ERROR: "error",
};
