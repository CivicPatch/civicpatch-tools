// Where a jurisdiction's activity lives, shared by the page that links to it and the page that
// is it. Constants only — importing `timeline.ts` for these would pull the whole activity
// component into the jurisdiction bundle.

// Mirrors the route in routers/frontend.py, registered ahead of the /{path:path} catch-all so
// this URL does not silently render the jurisdiction page instead.
export const ACTIVITY_PATH_SUFFIX = "/activity";

// The "In progress" section, which the jurisdiction page's in-flight badge links straight to.
export const IN_PROGRESS_ANCHOR = "in-progress";

export const activityUrl = (jurisdictionPath: string) =>
  `/${jurisdictionPath}${ACTIVITY_PATH_SUFFIX}`;
