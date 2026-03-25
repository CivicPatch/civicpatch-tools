import { useState, useEffect } from "haunted";
import {
  fetchReviewStats,
  fetchPullRequestDetail,
  getTodayReviewSession,
  passReviewSession,
  pauseReviewSession,
  navigateToEntry,
  mergePullRequest,
  closePullRequest,
} from "../../api.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";

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
  const [currentJob, setCurrentJob] = useState(null);
  const [currentPeople, setCurrentPeople] = useState(null);
  const [entryNumber, setEntryNumber] = useState(0);
  const [resolvedCount, setResolvedCount] = useState(0);
  const [hasNext, setHasNext] = useState(true);
  const [isNavigating, setIsNavigating] = useState(false);
  const [passedEntryNumbers, setPassedEntryNumbers] = useState(new Set());
  const [resolvedEntryNumbers, setResolvedEntryNumbers] = useState(new Set());
  const [frontierEntry, setFrontierEntry] = useState(0);
  const [prState, setPrState] = useState(null);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({ today_resolved: 0, streak: 0, all_time_resolved: 0, available_count: 0 });
  const [sourceContentUrls, setSourceContentUrls] = useState([]);

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
        if (data.current_entry) {
          await applyEntry(data.session.id, data.current_entry);
          onReviewing();
        } else {
          onIdle();
        }
      })
      .catch(() => onIdle());
  }, []);

  const applyEntry = async (sid, sessionData) => {
    const card = await fetchPullRequestDetail(sessionData.request_id);
    setCurrentJob(card.data.job);
    setCurrentPeople({ existing: card.data.existing, pull_request: card.data.pull_request });
    setEntryNumber(sessionData.entry_number);
    setFrontierEntry((prev) => Math.max(prev, sessionData.entry_number));
    setResolvedCount(sessionData.resolved_count ?? 0);

    const sourceMarkdownUrls = [...new Set(card.data.pull_request?.map(pr => pr.markdown_urls).flat())]
    setSourceContentUrls(sourceMarkdownUrls);
    updateParams({ state: stateCode, session: sid, request: sessionData.request_id });
  };

  const handleAdvanceResult = (sid, res) => {
    const data = res?.data;
    if (!data) {
      if (res?.reason === ADVANCE_DONE_REASON.NO_MORE_CARDS) {
        setHasNext(false);
      } else {
        updateParams({ state: stateCode, session: sid, request: null });
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
      const data = handleAdvanceResult(sid, res);
      if (!data) return;
      setHasNext(data.has_more !== false);
      await applyEntry(sid, data);
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
      const data = handleAdvanceResult(sid, res);
      if (!data) return;
      setHasNext(data.has_more !== false);
      await applyEntry(sid, data);
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
      let target = entryNumber - 1;
      while (target > 0 && passedEntryNumbers.has(target)) target--;
      const res = await navigateToEntry(session?.id, target);
      const data = res?.data;
      if (!data) return;
      await applyEntry(session?.id, data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsNavigating(false);
    }
  };

  const merge = async (event) => {
    const pullRequestNumber = event.detail.pullRequestNumber;
    setPrState({ status: PULL_REQUEST_STATUS.LOADING_MERGE });
    try {
      await mergePullRequest(pullRequestNumber);
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
      await applyEntry(session?.id, data);
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

  const close = async (event) => {
    const pullRequestNumber = event.detail.pullRequestNumber;
    setPrState({ status: PULL_REQUEST_STATUS.LOADING_CLOSE });
    try {
      await closePullRequest(pullRequestNumber);
      setPrState({ status: PULL_REQUEST_STATUS.CLOSED });
      setResolvedEntryNumbers((prev) => new Set([...prev, entryNumber]));
      await advance();
    } catch (err) {
      setPrState({ status: PULL_REQUEST_STATUS.ERROR, error: err.message });
    }
  };

  return {
    session, setSession,
    currentJob, currentPeople,
    entryNumber, resolvedCount,
    hasNext, isNavigating,
    prState, error, setError,
    stats,
    advance, back, pass, pause, merge, close, navigateTo,
    passedEntryNumbers, resolvedEntryNumbers, frontierEntry,
    sourceContentUrls
  };
}
