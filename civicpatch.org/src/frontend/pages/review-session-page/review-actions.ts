// The async orchestration behind the review session: fetch a card, navigate,
// merge/close, end. Plain functions that take an injected Effects bag — no
// haunted, no direct DOM — so they're unit-testable with fakes. use-review-session.ts
// wires the real api/dispatch/navigation into them.

import { REVIEW_STATUS } from "../../components/review-status.js";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";
import { landingUrl } from "../review-routes.js";
import { ActionType, ReviewMode, type CurrentEntry, type SessionMeta, type ReviewAction } from "./review-state.js";

const errMessage = (err: any) => err?.message ?? String(err);

const jurisdictionUrl = (ocdid: string) => `/${jurisdictionOcdidToPath(ocdid)}`;

// A server-sent review status, not one of the client-side action states the actions hook
// tracks. It was comparing against merged/closed, which the server stopped sending when
// publish state moved onto the request — so a decided scrape rendered as still editable.
const isTerminalStatus = (status: string | null | undefined) =>
  status === REVIEW_STATUS.PUBLISHED || status === REVIEW_STATUS.DISMISSED;

const belongsToSession = (active: any, changesetId: string | null) =>
  changesetId != null && (active?.session_request_ids ?? []).includes(changesetId);

// The injected boundary: everything the action functions touch that isn't pure.
// The hook fills this with the real api/DOM; tests pass fakes.
export type ReviewApi = {
  fetchActiveReviewSession: (stateCode: string) => Promise<any>;
  navigateToEntry: (sessionId: string, entryNumber: number) => Promise<any>;
  fetchReview: (changesetId: string) => Promise<any>;
  endReviewSession: (sessionId: string) => Promise<any>;
  fetchPullRequestByRequestId: (changesetId: string) => Promise<any>;
  saveReviewData: (changesetId: string, jurisdictionOcdid: string, people: any[]) => Promise<any>;
};

export type Effects = {
  api: ReviewApi;
  dispatch: (a: ReviewAction) => void;
  navigate: (url: string) => void;
  setRequestIdParam: (changesetId: string | null) => void;
  trackApprove: (changesetId: string, jurisdictionOcdid: string, people: any[] | null, jurisdictionName: string) => Promise<{ ok: boolean; error?: string }>;
  trackReject: (changesetId: string, jurisdictionName: string) => void;
};

// Assemble a CurrentEntry from a navigate/by-request response plus its review json.
export async function buildEntry(data: any, api: ReviewApi): Promise<CurrentEntry> {
  const review = await api.fetchReview(data.changeset_id).catch(() => null);
  return {
    changeset_id: data.changeset_id,
    jurisdiction: data.jurisdiction,
    pr: data.pr,
    mode: data.mode ?? ReviewMode.RECONCILE,
    pr_people: { existing: data.existing, proposed: data.proposed },
    // What the scrape would change about who holds what. A proposed person has no
    // membership — the post does not exist yet — so this is the only thing that can name
    // the post they would land in.
    changes: data.changes ?? [],
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
  e.setRequestIdParam(entry.changeset_id ?? null);
}

// `session_request_ids` is ordered by entry number, so position n is entry n + 1.
const entryNumberOf = (active: any, changesetId: string | null): number | null => {
  const at = (active?.session_request_ids ?? []).indexOf(changesetId);
  return at < 0 ? null : at + 1;
};

// Resumes at `changesetId` when the session holds it, otherwise where it was parked. That is
// what lets the url name a card and nothing else: whether a session is open, and where it
// left off, are things the session already knows.
async function resumeSession(
  active: any,
  stateCode: string,
  e: Effects,
  changesetId: string | null = null,
): Promise<void> {
  const entryNumber = entryNumberOf(active, changesetId) ?? active.current_entry_number;
  const data = (await e.api.navigateToEntry(active.session_id, entryNumber))?.data;
  if (!data) return e.navigate(landingUrl(stateCode));
  await loadFirstEntry(data, { id: active.session_id, daily_goal: active.daily_goal }, active.resolved_entry_numbers ?? [], e);
}

// A standalone deeplink may point at a stale/missing PR; treat a 404 as "no PR".
async function fetchPrOrNull(changesetId: string, api: ReviewApi): Promise<any> {
  try {
    return (await api.fetchPullRequestByRequestId(changesetId))?.data ?? null;
  } catch {
    return null;
  }
}

async function showStandaloneCard(changesetId: string, stateCode: string, e: Effects): Promise<void> {
  const data = await fetchPrOrNull(changesetId, e.api);
  if (!data) return e.navigate(landingUrl(stateCode));
  await loadFirstEntry(data, null, [], e);
}

// The url names a card and nothing else. A card the active session holds opens inside it, at
// that card; one it does not opens standalone; naming none resumes where the session was
// parked, or lands. Nothing about the session is in the url, because the session knows.
export async function boot(stateCode: string, changesetId: string | null, e: Effects): Promise<void> {
  try {
    const active = (await e.api.fetchActiveReviewSession(stateCode))?.data;
    if (active && (changesetId == null || belongsToSession(active, changesetId))) {
      return resumeSession(active, stateCode, e, changesetId);
    }
    if (changesetId != null) return showStandaloneCard(changesetId, stateCode, e);
    e.navigate(landingUrl(stateCode));
  } catch (err) {
    e.dispatch({ type: ActionType.LOAD_FAILED, payload: { message: errMessage(err) } });
  }
}

// No session means no queue, so there is nowhere to step to.
export async function goToEntry(sessionId: string | null, targetEntry: number, stateCode: string, e: Effects): Promise<void> {
  if (!sessionId) return;
  e.dispatch({ type: ActionType.NAV_STARTED });
  try {
    const data = (await e.api.navigateToEntry(sessionId, targetEntry))?.data;
    if (!data) return endSessionAndExit(sessionId, stateCode, e); // exhausted: server already ended it
    const entry = await buildEntry(data, e.api);
    e.dispatch({ type: ActionType.ENTRY_LOADED, payload: { current_entry: entry, entry_number: data.entry_number, total: data.total ?? data.entry_number } });
    e.setRequestIdParam(entry.changeset_id ?? null);
  } catch (err) {
    e.dispatch({ type: ActionType.LOAD_FAILED, payload: { message: errMessage(err) } });
  }
}

export async function endSessionAndExit(sessionId: string | null, stateCode: string, e: Effects): Promise<void> {
  if (sessionId) await e.api.endReviewSession(sessionId).catch(() => {});
  e.navigate(landingUrl(stateCode));
}

// Publishing or closing ends the PR's life. In a session that means the next entry;
// standalone there is no next, so it ends the flow back at the jurisdiction page.
async function advanceOrReturn(
  current: CurrentEntry,
  sessionId: string | null,
  entryNumber: number,
  stateCode: string,
  e: Effects,
): Promise<void> {
  if (sessionId) return goToEntry(sessionId, entryNumber + 1, stateCode, e);
  e.navigate(jurisdictionUrl(current.jurisdiction.ocdid!));
}

export async function mergeCurrent(current: CurrentEntry, sessionId: string | null, entryNumber: number, people: any[] | null, stateCode: string, e: Effects): Promise<void> {
  const { changeset_id, jurisdiction } = current;
  // No pull request check: publishing is keyed on the request, and a scrape committed
  // straight to open-data has no pull request to guard on.
  if (!changeset_id) return;
  const result = await e.trackApprove(changeset_id, jurisdiction.ocdid!, people, jurisdiction.name ?? changeset_id);
  if (!result.ok) {
    // Publishing is synchronous now, so a rejection is the whole outcome: flag the entry
    // red and keep the reviewer here to fix it.
    e.dispatch({ type: ActionType.MARK_FAILED, payload: { entry_number: entryNumber, message: result.error ?? "Publish failed." } });
    return;
  }
  e.dispatch({ type: ActionType.MARK_RESOLVED });
  await advanceOrReturn(current, sessionId, entryNumber, stateCode, e);
}

// Commit without publishing: the server has written `data_json` by the time this resolves,
// so the outcome is known here. A rejection keeps the reviewer on the entry, same as a
// failed publish.
export async function saveCurrent(current: CurrentEntry, sessionId: string | null, entryNumber: number, people: any[], stateCode: string, e: Effects): Promise<void> {
  const { changeset_id, jurisdiction } = current;
  if (!changeset_id) return;
  try {
    await e.api.saveReviewData(changeset_id, jurisdiction.ocdid!, people);
  } catch (err) {
    e.dispatch({ type: ActionType.MARK_FAILED, payload: { entry_number: entryNumber, message: errMessage(err) } });
    return;
  }
  e.dispatch({ type: ActionType.MARK_SAVED });
  // Save leaves the PR open, so standalone the reviewer stays on the card.
  await goToEntry(sessionId, entryNumber + 1, stateCode, e);
}

export async function closeCurrent(current: CurrentEntry, sessionId: string | null, entryNumber: number, stateCode: string, e: Effects): Promise<void> {
  const { changeset_id, jurisdiction } = current;
  if (!changeset_id) return;
  e.trackReject(changeset_id, jurisdiction.name ?? changeset_id);
  await advanceOrReturn(current, sessionId, entryNumber, stateCode, e);
}
