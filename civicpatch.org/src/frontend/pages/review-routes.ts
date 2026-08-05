// Shared route + query-param constants for the review landing (/review) and the
// review session (/review/session). Imported by both pages and the navbar so the
// URLs are built in exactly one place.

export const STATE_PARAM = "state";

// Where the session is: written back on every navigation so the url is shareable.
export const REQUEST_ID_PARAM = "request_id";

// Which single pull request to open, ignoring any session. Distinct from
// REQUEST_ID_PARAM because one url naming a card is ambiguous — a refresh mid-session
// and a link in from the jurisdiction page look identical, and mean opposite things.
export const PULL_REQUEST_PARAM = "pull_request";

// Which of the review card's three views is open. `view`, not `tab` — the
// jurisdiction page already uses `?tab=` to mean "which pull request", and the
// two would read as the same thing in a URL or a log line.
export const VIEW_PARAM = "view";

export const ReviewView = Object.freeze({
  OVERVIEW: "overview",
  DETAIL: "detail",
  PREVIEW: "preview",
});

export type ReviewViewKey = (typeof ReviewView)[keyof typeof ReviewView];

const VIEW_KEYS: ReviewViewKey[] = [
  ReviewView.OVERVIEW,
  ReviewView.DETAIL,
  ReviewView.PREVIEW,
];

// A URL is user-editable and outlives any release, so an unrecognised, removed
// or absent view falls back to Overview — the entry point for every card (§1)
// — rather than rendering nothing.
export function parseReviewView(value: string | null | undefined): ReviewViewKey {
  return VIEW_KEYS.includes(value as ReviewViewKey)
    ? (value as ReviewViewKey)
    : ReviewView.OVERVIEW;
}

export const REVIEW_PATH = "/review";
export const REVIEW_SESSION_PATH = "/review/session";

// Shared by anywhere that can start a review session (the /review landing page,
// and the homepage's Verify CTA). The key itself lives in STORAGE_KEYS.
export const DEFAULT_DAILY_GOAL = 10;

export const landingUrl = (stateCode: string) => `${REVIEW_PATH}?${STATE_PARAM}=${encodeURIComponent(stateCode)}`;
export const sessionUrl = (stateCode: string) => `${REVIEW_SESSION_PATH}?${STATE_PARAM}=${encodeURIComponent(stateCode)}`;

// One pull request, no session. What the jurisdiction page's Review button links to.
export const pullRequestUrl = (stateCode: string, requestId: string) =>
  `${sessionUrl(stateCode)}&${PULL_REQUEST_PARAM}=${encodeURIComponent(requestId)}`;
