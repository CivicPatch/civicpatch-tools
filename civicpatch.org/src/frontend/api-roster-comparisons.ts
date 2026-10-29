import {
  isOutcomeSelection,
  type PeopleSelection,
  type PersonComparison,
  type RosterComparisonListPage,
  type RosterComparisonSummary,
  type RunJurisdiction,
  type RunPeoplePage,
} from "./pages/roster-comparison-page/types.js";

const ROSTER_COMPARISONS_URL = "/api/v1/roster-comparisons";

// Status first: a 500 can be plain text, which would otherwise surface as a JSON syntax error.
async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${ROSTER_COMPARISONS_URL}${path}`, { credentials: "include" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export const fetchRosterComparisons = async (page: number, perPage: number) =>
  getJson<RosterComparisonListPage>(`?${new URLSearchParams({ page: String(page), per_page: String(perPage) })}`);

/** null leaves the choice to the server. */
function organizationParams(organizations: string[] | null): [string, string][] {
  return (organizations ?? []).map((name) => ["organizations", name]);
}

export const fetchRosterComparison = async (runId: string, organizations: string[] | null) =>
  (await getJson<{ data: RosterComparisonSummary }>(`/${runId}?${new URLSearchParams(organizationParams(organizations))}`))
    .data;

export const fetchRosterComparisonJurisdictions = async (runId: string, compared: boolean) =>
  (await getJson<{ data: RunJurisdiction[] }>(`/${runId}/jurisdictions?compared=${compared}`)).data;

export const fetchRosterComparisonJurisdiction = async (
  runId: string,
  jurisdictionOcdid: string,
  organizations: string[] | null,
) => {
  const params = new URLSearchParams(organizationParams(organizations));
  return (await getJson<{ data: PersonComparison[] }>(`/${runId}/jurisdictions/${jurisdictionOcdid}?${params}`)).data;
};

export const fetchRosterComparisonPeople = async (
  runId: string,
  selection: PeopleSelection,
  organizations: string[] | null,
  page: number,
  perPage: number,
) => {
  const filter = isOutcomeSelection(selection)
    ? { outcome: selection.outcome }
    : { field: selection.field, level: selection.filter };
  const params = new URLSearchParams({ ...filter, page: String(page), per_page: String(perPage) });
  organizationParams(organizations).forEach(([key, value]) => params.append(key, value));
  return getJson<RunPeoplePage>(`/${runId}/people?${params}`);
};
