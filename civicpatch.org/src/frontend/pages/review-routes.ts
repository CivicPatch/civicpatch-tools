// Shared route + query-param constants for the review landing (/review) and the
// review session (/review/session). Imported by both pages and the navbar so the
// URLs are built in exactly one place.

export const STATE_PARAM = "state";

// Which card is open. The only thing the url says: whether a session is running, and where
// it left off, are the session's own business.
export const CHANGESET_ID_PARAM = "changeset_id";

// The jurisdiction page is public; the review session is not. A signed-out visitor following
// a review link is bounced to the front page with no explanation, so the link offers sign-in
// instead. No return-to param: /login does not support one, and promising a bounce-back it
// will not honour is worse than landing them on the review list.
export const LOGIN_PATH = "/login";
export const REVIEW_PATH = "/review";
export const REVIEW_SESSION_PATH = "/review/session";

// Shared by anywhere that can start a review session (the /review landing page,
// and the homepage's Verify CTA). The key itself lives in STORAGE_KEYS.
export const DEFAULT_DAILY_GOAL = 10;

export const landingUrl = (stateCode: string) => `${REVIEW_PATH}?${STATE_PARAM}=${encodeURIComponent(stateCode)}`;
export const sessionUrl = (stateCode: string) => `${REVIEW_SESSION_PATH}?${STATE_PARAM}=${encodeURIComponent(stateCode)}`;

// One card, no session. What the jurisdiction page's Review button links to.
export const reviewSessionUrl = (stateCode: string, changesetId: string) =>
  `${sessionUrl(stateCode)}&${CHANGESET_ID_PARAM}=${encodeURIComponent(changesetId)}`;

