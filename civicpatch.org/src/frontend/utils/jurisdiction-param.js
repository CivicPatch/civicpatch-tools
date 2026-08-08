// The open modal is reflected in the URL: it survives a refresh, can be pasted to
// someone, and the back button closes it instead of leaving the page.
const JURISDICTION_PARAM = "jurisdiction";

export const readJurisdictionParam = () =>
  new URLSearchParams(window.location.search).get(JURISDICTION_PARAM) || "";

export const writeJurisdictionParam = (jurisdictionOcdid) => {
  const params = new URLSearchParams(window.location.search);
  if (jurisdictionOcdid) params.set(JURISDICTION_PARAM, jurisdictionOcdid);
  else params.delete(JURISDICTION_PARAM);

  const query = params.toString();
  // pushState, not a reload — the whole point is keeping the browse context behind it.
  window.history.pushState({}, "", query ? `?${query}` : window.location.pathname);
};
