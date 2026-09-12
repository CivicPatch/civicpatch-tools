// Shared route helpers for the municipalities/counties list pages, mirroring
// review-routes.ts's pattern — imported by both pages so the URL is built in one
// place. State here is a path segment (/{state}/municipalities, /{state}/counties),
// not a query param, so the navbar's default "patch ?state= on the current
// pathname" behavior would produce a broken URL (/wa?state=co) if a user switches
// state while already on this page.

const MUNICIPALITIES_PATH_RE = /^\/[a-z]{2}\/municipalities\/?$/i;
const COUNTIES_PATH_RE = /^\/[a-z]{2}\/counties\/?$/i;

export const municipalitiesUrl = (stateCode: string) => `/${stateCode}/municipalities`;
export const countiesUrl = (stateCode: string) => `/${stateCode}/counties`;

export const isMunicipalitiesPath = (path: string) => MUNICIPALITIES_PATH_RE.test(path);
export const isCountiesPath = (path: string) => COUNTIES_PATH_RE.test(path);
