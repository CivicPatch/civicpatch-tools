// Shared route helpers for the municipalities list page, mirroring review-routes.ts's
// pattern — imported by both this page and the navbar so the URL is built in one place.
// State here is a path segment (/{state}/local), not a query param, so the navbar's
// default "patch ?state= on the current pathname" behavior would produce a broken URL
// (/wa/local?state=co) if a user switches state while already on this page.

const MUNICIPALITIES_PATH_RE = /^\/[a-z]{2}\/local\/?$/i;

export const municipalitiesUrl = (stateCode: string) => `/${stateCode}/local`;

export const isMunicipalitiesPath = (path: string) => MUNICIPALITIES_PATH_RE.test(path);
