import { useState, useEffect } from "haunted";
import {
  fetchReviewStats,
  fetchReview,
  passReviewSession,
  pauseReviewSession,
  navigateToEntry,
  saveAndMerge,
} from "../../api.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";

const NO_MORE_CARDS = "no_more_cards";

export function updateParams(updates) {
  const p = new URLSearchParams(window.location.search);
  for (const [k, v] of Object.entries(updates)) {
    if (v == null) p.delete(k);
    else p.set(k, v);
  }
  history.replaceState(null, "", `?${p}`);
}

export function useReviewSession(stateCode, { onReviewing, onDone, onIdle }) {
  const [session, setSession] = useState(null);
  const [requestId, setRequestId] = useState(null);
  const [jurisdiction, setJurisdiction] = useState({ ocdid: null, name: null });
  const [pr, setPr] = useState({ url: null, status: null, reviewState: null });
  const [prPeople, setPrPeople] = useState(null);
  const [entryNumber, setEntryNumber] = useState(0);
  const [hasNext, setHasNext] = useState(true);
  const [hasPrev, setHasPrev] = useState(false);
  const [isNavigating, setIsNavigating] = useState(false);
  const [passedEntryNumbers, setPassedEntryNumbers] = useState(new Set());
  const [resolvedEntryNumbers, setResolvedEntryNumbers] = useState(new Set());
  const [frontierEntry, setFrontierEntry] = useState(0);
  const [mergeState, setMergeState] = useState(null);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({ today_resolved: 0, streak: 0, all_time_resolved: 0, available_count: 0, claimed_count: 0, best_streak: 0, avg_seconds_per_review: null });
  const [sourceContentUrls, setSourceContentUrls] = useState([]);
  const [reviewData, setReviewData] = useState(null);

  useEffect(() => {
    fetchReviewStats(stateCode).then((res) => setStats(res.data)).catch(() => {});
  }, [stateCode]);

  const applyEntry = async (sessionData) => {
    const review = await fetchReview(sessionData.request_id).catch(() => null);
    setRequestId(sessionData.request_id);
    setJurisdiction(sessionData.jurisdiction);
    setPr(sessionData.pr);
    setPrPeople({ existing: sessionData.existing, proposed: sessionData.proposed });
    setEntryNumber(sessionData.entry_number);
    setFrontierEntry((prev) => Math.max(prev, sessionData.entry_number));
    setHasPrev(sessionData.has_prev ?? false);
    setReviewData(review?.data ?? null);
    setSourceContentUrls(sessionData.sources);
    updateParams({ state: stateCode });
  };

  const handleAdvanceResult = (res) => {
    const data = res?.data;
    if (!data) {
      if (res?.reason === NO_MORE_CARDS) {
        setHasNext(false);
      } else {
        updateParams({ state: stateCode });
        onDone();
      }
      return null;
    }
    return data;
  };

  const advance = async (sessionId) => {
    const sid = sessionId ?? session?.id;
    setMergeState(null);
    setIsNavigating(true);
    try {
      let target = entryNumber + 1;
      while (passedEntryNumbers.has(target)) target++;
      const res = await navigateToEntry(sid, target);
      const data = handleAdvanceResult(res);
      if (!data) return;
      setHasNext(data.has_next !== false);
      await applyEntry(data);
      onReviewing();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsNavigating(false);
    }
  };

  const pass = async () => {
    const sid = session?.id;
    const passed = entryNumber;
    setMergeState(null);
    setIsNavigating(true);
    try {
      await passReviewSession(sid, passed);
      const nextPassedSet = new Set([...passedEntryNumbers, passed]);
      setPassedEntryNumbers(nextPassedSet);
      let target = passed + 1;
      while (nextPassedSet.has(target)) target++;
      const res = await navigateToEntry(sid, target);
      const data = handleAdvanceResult(res);
      if (!data) return;
      setHasNext(data.has_next !== false);
      await applyEntry(data);
      onReviewing();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsNavigating(false);
    }
  };

  const back = async () => {
    setMergeState(null);
    setIsNavigating(true);
    try {
      const res = await navigateToEntry(session?.id, entryNumber - 1);
      const data = res?.data;
      if (!data) return;
      await applyEntry(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsNavigating(false);
    }
  };

  const merge = async (people) => {
    const pullRequestNumber = pr.number;
    setMergeState({ status: PULL_REQUEST_STATUS.LOADING_MERGE });
    try {
      await saveAndMerge(pullRequestNumber, requestId, jurisdiction.ocdid, people ?? null);
      setMergeState({ status: PULL_REQUEST_STATUS.MERGED });
      setResolvedEntryNumbers((prev) => new Set([...prev, entryNumber]));
      await advance();
    } catch (err) {
      setMergeState({ status: PULL_REQUEST_STATUS.ERROR, error: err.message });
    }
  };

  const navigateTo = async (n) => {
    setMergeState(null);
    setIsNavigating(true);
    try {
      const res = await navigateToEntry(session?.id, n);
      const data = res?.data;
      if (!data) return;
      setHasNext(data.has_next !== false);
      await applyEntry(data);
      onReviewing();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsNavigating(false);
    }
  };

  const pause = async () => {
    const sid = session?.id;
    if (!sid) return;
    await pauseReviewSession(sid);
    onIdle();
  };

  return {
    session, setSession,
    jurisdiction,
    pr,
    progress: { entryNumber, hasNext, hasPrev, passedEntryNumbers, resolvedEntryNumbers, frontierEntry, isNavigating },
    prPeople,
    mergeState, error, setError,
    stats,
    advance, back, pass, pause, merge, navigateTo,
    sourceContentUrls, reviewData,
  };
}
