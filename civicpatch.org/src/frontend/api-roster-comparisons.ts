import {
  isOutcomeSelection,
  type PeopleSelection,
  type PersonComparison,
  type RosterComparisonListPage,
  type RosterComparisonSummary,
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

export const fetchRosterComparison = async (runId: string) =>
  (await getJson<{ data: RosterComparisonSummary }>(`/${runId}`)).data;

export const fetchRosterComparisonJurisdiction = async (runId: string, jurisdictionOcdid: string) =>
  (await getJson<{ data: PersonComparison[] }>(`/${runId}/jurisdictions/${jurisdictionOcdid}`)).data;

export const fetchRosterComparisonPeople = async (
  runId: string,
  selection: PeopleSelection,
  page: number,
  perPage: number,
) => {
  const filter = isOutcomeSelection(selection)
    ? { outcome: selection.outcome }
    : { field: selection.field, level: selection.filter };
  const params = new URLSearchParams({ ...filter, page: String(page), per_page: String(perPage) });
  return getJson<RunPeoplePage>(`/${runId}/people?${params}`);
};
