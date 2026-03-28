import { useState, useEffect } from "haunted";
import {
  fetchReviewStats,
  fetchPullRequestDetail,
  fetchReview,
  getTodayReviewSession,
  passReviewSession,
  pauseReviewSession,
  navigateToEntry,
  mergePullRequest,
  updatePullRequestBranch,
  updatePullRequestData,
} from "../../api.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";
import { pullRequestUrlToNumber } from "../../components/pull-request-card/pr-utils.js";
import { useLocalStorage } from "../../hooks/use-local-storage.js";

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
  const [storedEntry, setStoredEntry] = useLocalStorage("review_current_entry", null);

  useEffect(() => {
    fetchReviewStats(stateCode).then((res) => setStats(res.data)).catch(() => {});
  }, [stateCode]);

  useEffect(() => {
    getTodayReviewSession(stateCode)
      .then(async (res) => {
        const data = res?.data;
        if (!data) { onIdle(); return; }
        setSession(data.session);
        const loadedPassed = new Set(data.passed_entry_numbers || []);
        setPassedEntryNumbers(loadedPassed);
        const allVisited = [data.current_entry?.entry_number, ...(data.passed_entry_numbers || [])].filter(Boolean);
        setFrontierEntry(allVisited.length > 0 ? Math.max(...allVisited) : 0);
        if (storedEntry?.state_code === stateCode) {
          const res = await navigateToEntry(data.session.id, storedEntry.entry_number);
          const entryData = res?.data;
          if (entryData) {
            await applyEntry(entryData);
            onReviewing();
            return;
          }
        }
        onIdle();
      })
      .catch(() => onIdle());
  }, []);

  const applyEntry = async (sessionData) => {
    const [card, review] = await Promise.all([
      fetchPullRequestDetail(sessionData.request_id),
      fetchReview(sessionData.request_id).catch(() => null),
    ]);
    setRequestId(sessionData.request_id);
    setJurisdictionOcdid(sessionData.jurisdiction_ocdid);
    setPullRequestUrl(card.data.request?.pull_request_url ?? null);
    setJurisdictionName(card.data.request?.jurisdiction_name ?? null);
    setCurrentPeople({ existing: card.data.existing, pull_request: card.data.pull_request });
    setEntryNumber(sessionData.entry_number);
    setFrontierEntry((prev) => Math.max(prev, sessionData.entry_number));
    setResolvedCount(sessionData.resolved_count ?? 0);
    setHasPrev(sessionData.has_prev ?? false);
    setReviewData(review?.data ?? null);

    setSourceContentUrls(card.data.sources);
    setStoredEntry({ state_code: stateCode, entry_number: sessionData.entry_number });
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
      if (people) await updatePullRequestData(requestId, jurisdictionOcdid, people);
      await mergePullRequest(requestId, pullRequestNumber);
      setPrState({ status: PULL_REQUEST_STATUS.MERGED });
      setResolvedEntryNumbers((prev) => new Set([...prev, entryNumber]));
      await advance();
    } catch (err) {
      if (err.status === 409) {
        setPrState({ status: PULL_REQUEST_STATUS.BRANCH_OUT_OF_DATE });
      } else {
        setPrState({ status: PULL_REQUEST_STATUS.ERROR, error: err.message });
      }
    }
  };

  const updateBranch = async () => {
    const pullRequestNumber = pullRequestUrlToNumber(pullRequestUrl);
    setPrState({ status: PULL_REQUEST_STATUS.LOADING_UPDATE_BRANCH });
    try {
      await updatePullRequestBranch(pullRequestNumber);
      setPrState(null);
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

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState !== "visible" || !session) return;
      const today = new Date().toISOString().split("T")[0];
      if (session.session_date !== today) {
        setSession(null);
        setStoredEntry(null);
        onIdle();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => document.removeEventListener("visibilitychange", handleVisibilityChange);
  }, [session]);

  const pause = async () => {
    const sid = session?.id;
    if (!sid) return;
    await pauseReviewSession(sid);
    setStoredEntry(null);
    onIdle();
  };

  return {
    session, setSession,
    requestId, jurisdictionOcdid, pullRequestUrl, jurisdictionName,
    currentPeople,
    entryNumber, resolvedCount,
    hasNext, hasPrev, isNavigating,
    prState, error, setError,
    stats,
    advance, back, pass, pause, merge, updateBranch, navigateTo,
    passedEntryNumbers, resolvedEntryNumbers, frontierEntry,
    sourceContentUrls, reviewData
  };
}
