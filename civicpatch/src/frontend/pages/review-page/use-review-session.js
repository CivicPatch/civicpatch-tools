import { useState, useEffect } from "haunted";
import {
  fetchReviewStats,
  fetchPullRequestDetail,
  fetchReview,
  passReviewSession,
  pauseReviewSession,
  navigateToEntry,
  saveAndMerge,
} from "../../api.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import { pullRequestUrlToNumber } from "../../components/pull-request-card/pr-utils.js";

const ADVANCE_DONE_REASON = {
  GOAL_REACHED: "goal_reached",
  NO_MORE_CARDS: "no_more_cards",
};

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
  const [jurisdictionOcdid, setJurisdictionOcdid] = useState(null);
  const [pullRequestUrl, setPullRequestUrl] = useState(null);
  const [jurisdictionName, setJurisdictionName] = useState(null);
  const [reviewState, setReviewState] = useState(null);
  const [pullRequestStatus, setPullRequestStatus] = useState(null);
  const [currentPeople, setCurrentPeople] = useState(null);
  const [entryNumber, setEntryNumber] = useState(0);
  const [resolvedCount, setResolvedCount] = useState(0);
  const [hasNext, setHasNext] = useState(true);
  const [hasPrev, setHasPrev] = useState(false);
  const [isNavigating, setIsNavigating] = useState(false);
  const [passedEntryNumbers, setPassedEntryNumbers] = useState(new Set());
  const [resolvedEntryNumbers, setResolvedEntryNumbers] = useState(new Set());
  const [frontierEntry, setFrontierEntry] = useState(0);
  const [prState, setPrState] = useState(null);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({ today_resolved: 0, streak: 0, all_time_resolved: 0, available_count: 0, claimed_count: 0 });
  const [sourceContentUrls, setSourceContentUrls] = useState([]);
  const [reviewData, setReviewData] = useState(null);

  useEffect(() => {
    fetchReviewStats(stateCode).then((res) => setStats(res.data)).catch(() => {});
  }, [stateCode]);

  const applyEntry = async (sessionData) => {
    const [card, review] = await Promise.all([
      fetchPullRequestDetail(sessionData.request_id),
      fetchReview(sessionData.request_id).catch(() => null),
    ]);
    setRequestId(sessionData.request_id);
    setJurisdictionOcdid(sessionData.jurisdiction_ocdid);
    setPullRequestUrl(card.data.request?.pull_request_url ?? null);
    setJurisdictionName(card.data.request?.jurisdiction_name ?? null);
    setReviewState(card.data.request?.pull_request_review_state ?? null);
    setPullRequestStatus(card.data.request?.pull_request_status ?? null);
    setCurrentPeople({ existing: card.data.existing, pull_request: card.data.pull_request });
    setEntryNumber(sessionData.entry_number);
    setFrontierEntry((prev) => Math.max(prev, sessionData.entry_number));
    setResolvedCount(sessionData.resolved_count ?? 0);
    setHasPrev(sessionData.has_prev ?? false);
    setReviewData(review?.data ?? null);

    setSourceContentUrls(card.data.sources);
    updateParams({ state: stateCode });
  };

  const handleAdvanceResult = (res) => {
    const data = res?.data;
    if (!data) {
      if (res?.reason === ADVANCE_DONE_REASON.NO_MORE_CARDS) {
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
    setPrState(null);
    setIsNavigating(true);
    try {
      let target = entryNumber + 1;
      while (passedEntryNumbers.has(target)) target++;
      const res = await navigateToEntry(sid, target);
      const data = handleAdvanceResult(res);
      if (!data) return;
      setHasNext(data.has_more !== false);
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
    setPrState(null);
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
      setHasNext(data.has_more !== false);
      await applyEntry(data);
      onReviewing();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsNavigating(false);
    }
  };

  const back = async () => {
    setPrState(null);
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
    const pullRequestNumber = pullRequestUrlToNumber(pullRequestUrl);
    setPrState({ status: PULL_REQUEST_STATUS.LOADING_MERGE });
    try {
      await saveAndMerge(pullRequestNumber, requestId, jurisdictionOcdid, people ?? null);
      setPrState({ status: PULL_REQUEST_STATUS.MERGED });
      setResolvedEntryNumbers((prev) => new Set([...prev, entryNumber]));
      await advance();
    } catch (err) {
      setPrState({ status: PULL_REQUEST_STATUS.ERROR, error: err.message });
    }
  };

  const navigateTo = async (n) => {
    setPrState(null);
    setIsNavigating(true);
    try {
      const res = await navigateToEntry(session?.id, n);
      const data = res?.data;
      if (!data) return;
      setHasNext(data.has_more !== false);
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
    requestId, jurisdictionOcdid, pullRequestUrl, jurisdictionName, reviewState, pullRequestStatus,
    currentPeople,
    entryNumber, resolvedCount,
    hasNext, hasPrev, isNavigating,
    prState, error, setError,
    stats,
    advance, back, pass, pause, merge, navigateTo,
    passedEntryNumbers, resolvedEntryNumbers, frontierEntry,
    sourceContentUrls, reviewData
  };
}
