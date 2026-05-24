import { useReducer, useEffect } from "haunted";
import {
  fetchActiveReviewSession,
  navigateToEntry,
  fetchReview,
  endReviewSession,
  fetchPullRequestByNumber,
  fetchReviewStats,
} from "../../api.js";
import { reduceReview, initialPageState, ActionType, StateKind } from "./review-state.js";
import { boot, goToEntry, endSessionAndExit, mergeCurrent, closeCurrent, type Effects } from "./review-actions.js";
import { PR_NUMBER_PARAM } from "../review-routes.js";

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
