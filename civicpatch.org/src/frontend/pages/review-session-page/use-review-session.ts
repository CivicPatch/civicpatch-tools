import { useReducer, useEffect } from "haunted";
import {
  fetchActiveReviewSession,
  navigateToEntry,
  fetchReview,
  endReviewSession,
  fetchPullRequestByNumber,
  fetchReviewStats,
} from "../../api.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import { reduceReview, initialPageState, ActionType, StateKind, type CurrentEntry, type SessionMeta, type ReviewAction } from "./review-state.js";

export const STATE_PARAM = "state";
const PR_NUMBER_PARAM = "pull_request_number";

export function updateParams(updates: Record<string, string | null | undefined>) {
  const p = new URLSearchParams(window.location.search);
  for (const [k, v] of Object.entries(updates)) {
    if (v == null) p.delete(k);
    else p.set(k, v);
  }
  history.replaceState(null, "", `?${p}`);
}

export const landingUrl = (stateCode: string) => `/review?${STATE_PARAM}=${encodeURIComponent(stateCode)}`;

const errMessage = (err: any) => err?.message ?? String(err);

const isTerminalStatus = (status: string | null | undefined) =>
  status === PULL_REQUEST_STATUS.MERGED || status === PULL_REQUEST_STATUS.CLOSED;

const belongsToSession = (active: any, prNumber: number | null) =>
  prNumber != null && (active?.session_pull_request_numbers ?? []).includes(prNumber);

// The injected boundary: everything the action functions touch that isn't pure.
// The hook fills this with the real api/DOM; tests pass fakes.
export type ReviewApi = {
  fetchActiveReviewSession: typeof fetchActiveReviewSession;
  navigateToEntry: typeof navigateToEntry;
  fetchReview: typeof fetchReview;
  endReviewSession: typeof endReviewSession;
  fetchPullRequestByNumber: typeof fetchPullRequestByNumber;
};

export type Effects = {
  api: ReviewApi;
  dispatch: (a: ReviewAction) => void;
  navigate: (url: string) => void;
  setPrParam: (prNumber: number | null) => void;
  trackMerge: (prNumber: number, requestId: string, jurisdictionOcdid: string, people: any[] | null, jurisdictionName: string) => void;
  trackClose: (prNumber: number, requestId: string, jurisdictionName: string) => void;
};

// Assemble a CurrentEntry from a navigate/by-number response plus its review json.
export async function buildEntry(data: any, api: ReviewApi): Promise<CurrentEntry> {
  const review = await api.fetchReview(data.request_id).catch(() => null);
  return {
    request_id: data.request_id,
    jurisdiction: data.jurisdiction,
    pr: data.pr,
    pr_people: { existing: data.existing, proposed: data.proposed },
    review_data: review?.data ?? null,
    source_content_urls: data.sources,
    is_read_only: isTerminalStatus(data.pr?.status),
    has_next: data.has_next ?? false,
  };
}

// The first card of the page is always a SESSION_LOADED — session is null for a
// standalone deeplink. setPrParam reflects the card into the URL for shareability.
async function loadFirstEntry(data: any, session: SessionMeta | null, resolvedEntryNumbers: number[], e: Effects): Promise<void> {
  const entry = await buildEntry(data, e.api);
  e.dispatch({
    type: ActionType.SESSION_LOADED,
    payload: { current_entry: entry, entry_number: data.entry_number ?? 1, session, resolved_entry_numbers: resolvedEntryNumbers },
  });
  e.setPrParam(entry.pr.number ?? null);
}

async function resumeSession(active: any, stateCode: string, e: Effects): Promise<void> {
  const data = (await e.api.navigateToEntry(active.session_id, active.current_entry_number))?.data;
  if (!data) return e.navigate(landingUrl(stateCode));
  await loadFirstEntry(data, { id: active.session_id, daily_goal: active.daily_goal }, active.resolved_entry_numbers ?? [], e);
}

async function showStandalonePr(prNumber: number, stateCode: string, e: Effects): Promise<void> {
  const data = (await e.api.fetchPullRequestByNumber(prNumber))?.data;
  if (!data) return e.navigate(landingUrl(stateCode));
  await loadFirstEntry(data, null, [], e);
}

// ── Action functions (plain, testable; no haunted) ────────────────────────────

// A deeplink to one of the session's own PRs (e.g. a refresh) stays in session
// mode; a deeplink to any other PR wins and shows it standalone. With no PR in
// the URL we resume the active session, falling back to the landing page.
export async function boot(stateCode: string, prNumber: number | null, e: Effects): Promise<void> {
  try {
    const active = (await e.api.fetchActiveReviewSession(stateCode))?.data;
    if (active && (prNumber == null || belongsToSession(active, prNumber))) return resumeSession(active, stateCode, e);
    if (prNumber != null) return showStandalonePr(prNumber, stateCode, e);
    e.navigate(landingUrl(stateCode));
  } catch (err) {
    e.dispatch({ type: ActionType.LOAD_FAILED, payload: { message: errMessage(err) } });
  }
}

export async function goToEntry(sessionId: string, targetEntry: number, stateCode: string, e: Effects): Promise<void> {
  e.dispatch({ type: ActionType.NAV_STARTED });
  try {
    const data = (await e.api.navigateToEntry(sessionId, targetEntry))?.data;
    if (!data) return endSessionAndExit(sessionId, stateCode, e); // exhausted: server already ended it
    const entry = await buildEntry(data, e.api);
    e.dispatch({ type: ActionType.ENTRY_LOADED, payload: { current_entry: entry, entry_number: data.entry_number } });
    e.setPrParam(entry.pr.number ?? null);
  } catch (err) {
    e.dispatch({ type: ActionType.LOAD_FAILED, payload: { message: errMessage(err) } });
  }
}

export async function endSessionAndExit(sessionId: string | null, stateCode: string, e: Effects): Promise<void> {
  if (sessionId) await e.api.endReviewSession(sessionId).catch(() => {});
  e.navigate(landingUrl(stateCode));
}

export async function mergeCurrent(current: CurrentEntry, sessionId: string, entryNumber: number, people: any[] | null, stateCode: string, e: Effects): Promise<void> {
  const { pr, request_id, jurisdiction } = current;
  if (!pr?.number || !request_id) return;
  e.trackMerge(pr.number, request_id, jurisdiction.ocdid!, people, jurisdiction.name ?? `#${pr.number}`);
  e.dispatch({ type: ActionType.MARK_RESOLVED });
  await goToEntry(sessionId, entryNumber + 1, stateCode, e);
}

export async function closeCurrent(current: CurrentEntry, sessionId: string, entryNumber: number, stateCode: string, e: Effects): Promise<void> {
  const { pr, request_id, jurisdiction } = current;
  if (!pr?.number || !request_id) return;
  e.trackClose(pr.number, request_id, jurisdiction.name ?? `#${pr.number}`);
  await goToEntry(sessionId, entryNumber + 1, stateCode, e);
}

// ── The haunted hook: wires the reducer to the action functions ───────────────

export function useReviewSession(
  stateCode: string,
  deps: { trackMerge: Effects["trackMerge"]; trackClose: Effects["trackClose"]; navigate?: (url: string) => void },
) {
  const [state, dispatch] = useReducer(reduceReview, initialPageState(stateCode));

  const effects: Effects = {
    api: { fetchActiveReviewSession, navigateToEntry, fetchReview, endReviewSession, fetchPullRequestByNumber },
    dispatch,
    navigate: deps.navigate ?? ((url) => { window.location.href = url; }),
    setPrParam: (prNumber) => updateParams({ [PR_NUMBER_PARAM]: prNumber != null ? String(prNumber) : null }),
    trackMerge: deps.trackMerge,
    trackClose: deps.trackClose,
  };

  // Load the first card once on mount; stats load in parallel.
  useEffect(() => {
    const prParam = new URLSearchParams(window.location.search).get(PR_NUMBER_PARAM);
    boot(stateCode, prParam ? parseInt(prParam, 10) : null, effects);
    fetchReviewStats(stateCode)
      .then((res) => dispatch({ type: ActionType.STATS_LOADED, payload: { stats: res.data } }))
      .catch(() => {});
  }, []);

  const reviewing = state.fsm.kind === StateKind.REVIEWING ? state.fsm : null;
  const sessionId = reviewing?.session?.id ?? "";
  const entryNumber = reviewing?.entry_number ?? 0;
  const ready = !!reviewing && !reviewing.busy;

  return {
    fsm: state.fsm,
    stats: state.stats,
    advance: () => { if (ready) goToEntry(sessionId, entryNumber + 1, stateCode, effects); },
    back: () => { if (ready) goToEntry(sessionId, entryNumber - 1, stateCode, effects); },
    navigateTo: (n: number) => { if (ready) goToEntry(sessionId, n, stateCode, effects); },
    merge: (people: any[] | null) => { if (ready && reviewing) mergeCurrent(reviewing.current_entry, sessionId, entryNumber, people, stateCode, effects); },
    closePr: () => { if (ready && reviewing) closeCurrent(reviewing.current_entry, sessionId, entryNumber, stateCode, effects); },
    endSession: () => { if (reviewing) endSessionAndExit(reviewing.session?.id ?? null, stateCode, effects); },
  };
}
