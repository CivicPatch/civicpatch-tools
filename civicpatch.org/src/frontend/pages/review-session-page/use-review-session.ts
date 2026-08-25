import { useReducer, useEffect } from "haunted";
import {
  fetchActiveReviewSession,
  navigateToEntry,
  fetchReview,
  endReviewSession,
  fetchPullRequestByRequestId,
  fetchReviewStats,
  saveReviewData,
} from "../../api.js";
import { reduceReview, initialPageState, ActionType, StateKind } from "./review-state.js";
import { boot, goToEntry, endSessionAndExit, mergeCurrent, saveCurrent, closeCurrent, type Effects } from "./review-actions.js";
import { REQUEST_ID_PARAM } from "../review-routes.js";

export function updateParams(updates: Record<string, string | null | undefined>) {
  const p = new URLSearchParams(window.location.search);
  for (const [k, v] of Object.entries(updates)) {
    if (v == null) p.delete(k);
    else p.set(k, v);
  }
  history.replaceState(null, "", `?${p}`);
}

export function useReviewSession(
  stateCode: string,
  deps: { trackApprove: Effects["trackApprove"]; trackReject: Effects["trackReject"]; navigate?: (url: string) => void },
) {
  const [state, dispatch] = useReducer(reduceReview, initialPageState(stateCode));

  const effects: Effects = {
    api: { fetchActiveReviewSession, navigateToEntry, fetchReview, endReviewSession, fetchPullRequestByRequestId, saveReviewData },
    dispatch,
    navigate: deps.navigate ?? ((url) => { window.location.href = url; }),
    setRequestIdParam: (requestId) => updateParams({ [REQUEST_ID_PARAM]: requestId }),
    trackApprove: deps.trackApprove,
    trackReject: deps.trackReject,
  };

  // Load the first card once on mount; stats load in parallel.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    boot(stateCode, params.get(REQUEST_ID_PARAM), effects);
    fetchReviewStats(stateCode)
      .then((res) => dispatch({ type: ActionType.STATS_LOADED, payload: { stats: res.data } }))
      .catch(() => {});
  }, []);

  const reviewing = state.fsm.kind === StateKind.REVIEWING ? state.fsm : null;
  // null, not "", for a standalone deeplink: an empty id builds
  // /review-sessions//navigate, which 405s.
  const sessionId = reviewing?.session?.id ?? null;
  const entryNumber = reviewing?.entry_number ?? 0;
  const ready = !!reviewing && !reviewing.busy;

  return {
    fsm: state.fsm,
    stats: state.stats,
    advance: () => { if (ready) goToEntry(sessionId, entryNumber + 1, stateCode, effects); },
    back: () => { if (ready) goToEntry(sessionId, entryNumber - 1, stateCode, effects); },
    navigateTo: (n: number) => { if (ready) goToEntry(sessionId, n, stateCode, effects); },
    merge: (people: any[] | null) => { if (ready && reviewing) mergeCurrent(reviewing.current_entry, sessionId, entryNumber, people, stateCode, effects); },
    save: (people: any[]) => { if (ready && reviewing) saveCurrent(reviewing.current_entry, sessionId, entryNumber, people, stateCode, effects); },
    rejectScrape: () => { if (ready && reviewing) closeCurrent(reviewing.current_entry, sessionId, entryNumber, stateCode, effects); },
    endSession: () => { if (reviewing) endSessionAndExit(reviewing.session?.id ?? null, stateCode, effects); },
  };
}
