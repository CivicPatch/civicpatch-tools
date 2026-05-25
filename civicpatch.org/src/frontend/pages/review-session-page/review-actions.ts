// The async orchestration behind the review session: fetch a card, navigate,
// merge/close, end. Plain functions that take an injected Effects bag — no
// haunted, no direct DOM — so they're unit-testable with fakes. use-review-session.ts
// wires the real api/dispatch/navigation into them.

import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import { landingUrl } from "../review-routes.js";
import { ActionType, type CurrentEntry, type SessionMeta, type ReviewAction } from "./review-state.js";

const errMessage = (err: any) => err?.message ?? String(err);

const isTerminalStatus = (status: string | null | undefined) =>
  status === PULL_REQUEST_STATUS.MERGED || status === PULL_REQUEST_STATUS.CLOSED;

const belongsToSession = (active: any, requestId: string | null) =>
  requestId != null && (active?.session_request_ids ?? []).includes(requestId);

// The injected boundary: everything the action functions touch that isn't pure.
// The hook fills this with the real api/DOM; tests pass fakes.
export type ReviewApi = {
  fetchActiveReviewSession: (stateCode: string) => Promise<any>;
  navigateToEntry: (sessionId: string, entryNumber: number) => Promise<any>;
  fetchReview: (requestId: string) => Promise<any>;
  endReviewSession: (sessionId: string) => Promise<any>;
  fetchPullRequestByRequestId: (requestId: string) => Promise<any>;
};

export type Effects = {
  api: ReviewApi;
  dispatch: (a: ReviewAction) => void;
  navigate: (url: string) => void;
  setRequestIdParam: (requestId: string | null) => void;
  trackMerge: (prNumber: number, requestId: string, jurisdictionOcdid: string, people: any[] | null, jurisdictionName: string) => void;
  trackClose: (prNumber: number, requestId: string, jurisdictionName: string) => void;
};

// Assemble a CurrentEntry from a navigate/by-request response plus its review json.
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
// standalone deeplink. setRequestIdParam reflects the card into the URL for shareability.
async function loadFirstEntry(data: any, session: SessionMeta | null, resolvedEntryNumbers: number[], e: Effects): Promise<void> {
  const entry = await buildEntry(data, e.api);
  e.dispatch({
    type: ActionType.SESSION_LOADED,
    payload: { current_entry: entry, entry_number: data.entry_number ?? 1, total: data.total ?? data.entry_number ?? 1, session, resolved_entry_numbers: resolvedEntryNumbers },
  });
  e.setRequestIdParam(entry.request_id ?? null);
}

async function resumeSession(active: any, stateCode: string, e: Effects): Promise<void> {
  const data = (await e.api.navigateToEntry(active.session_id, active.current_entry_number))?.data;
  if (!data) return e.navigate(landingUrl(stateCode));
  await loadFirstEntry(data, { id: active.session_id, daily_goal: active.daily_goal }, active.resolved_entry_numbers ?? [], e);
}

// A standalone deeplink may point at a stale/missing PR; treat a 404 as "no PR".
async function fetchPrOrNull(requestId: string, api: ReviewApi): Promise<any> {
  try {
    return (await api.fetchPullRequestByRequestId(requestId))?.data ?? null;
  } catch {
    return null;
  }
}

async function showStandalonePr(requestId: string, stateCode: string, e: Effects): Promise<void> {
  const data = await fetchPrOrNull(requestId, e.api);
  if (!data) return e.navigate(landingUrl(stateCode));
  await loadFirstEntry(data, null, [], e);
}

// A deeplink to one of the session's own PRs (e.g. a refresh) stays in session
// mode; a deeplink to any other PR wins and shows it standalone. With no PR in
// the URL we resume the active session, falling back to the landing page.
export async function boot(stateCode: string, requestId: string | null, e: Effects): Promise<void> {
  try {
    const active = (await e.api.fetchActiveReviewSession(stateCode))?.data;
    if (active && (requestId == null || belongsToSession(active, requestId))) return resumeSession(active, stateCode, e);
    if (requestId != null) return showStandalonePr(requestId, stateCode, e);
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
    e.dispatch({ type: ActionType.ENTRY_LOADED, payload: { current_entry: entry, entry_number: data.entry_number, total: data.total ?? data.entry_number } });
    e.setRequestIdParam(entry.request_id ?? null);
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
