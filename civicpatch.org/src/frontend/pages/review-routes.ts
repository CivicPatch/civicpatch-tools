// Shared route + query-param constants for the review landing (/review) and the
// review session (/review/session). Imported by both pages and the navbar so the
// URLs are built in exactly one place.

export const STATE_PARAM = "state";
export const REQUEST_ID_PARAM = "request_id";

export const REVIEW_PATH = "/review";
export const REVIEW_SESSION_PATH = "/review/session";

export const landingUrl = (stateCode: string) => `${REVIEW_PATH}?${STATE_PARAM}=${encodeURIComponent(stateCode)}`;
export const sessionUrl = (stateCode: string) => `${REVIEW_SESSION_PATH}?${STATE_PARAM}=${encodeURIComponent(stateCode)}`;
