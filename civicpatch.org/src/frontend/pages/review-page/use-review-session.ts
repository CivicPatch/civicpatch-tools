import { useState, useEffect } from "haunted";
import {
  fetchReviewStats,
  fetchReview,
  fetchPullRequestByNumber,
  endReviewSession,
  navigateToEntry,
  kickOffMerge,
} from "../../api.js";
import { useWebSocket } from "../../hooks/use-websocket.js";

const MERGE_TOPIC_PREFIX = "merge:";
const MERGE_EVENT_ERROR = "merge_error";

export function updateParams(updates: Record<string, string | null | undefined>) {
  const p = new URLSearchParams(window.location.search);
  for (const [k, v] of Object.entries(updates)) {
    if (v == null) p.delete(k);
    else p.set(k, v);
  }
  history.replaceState(null, "", `?${p}`);
}

export function useReviewSession(stateCode, { onReviewing, onDone, onIdle, userId }) {
  const [session, setSession] = useState<{ id: string; daily_goal: number } | null>(null);
  const [requestId, setRequestId] = useState<string | null>(null);
  const [jurisdiction, setJurisdiction] = useState({ ocdid: null, name: null });
  const [pr, setPr] = useState<{ url: string | null; status: string | null; reviewState: string | null; number?: number | null }>({ url: null, status: null, reviewState: null });
  const [prPeople, setPrPeople] = useState<{ existing: any[]; proposed: any[] } | null>(null);
  const [entryNumber, setEntryNumber] = useState(0);
  const [isNavigating, setIsNavigating] = useState(false);
  const [resolvedEntryNumbers, setResolvedEntryNumbers] = useState(new Set());
  const [frontierEntry, setFrontierEntry] = useState(0);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({ today_resolved: 0, streak: 0, all_time_resolved: 0, available_count: 0, claimed_count: 0, best_streak: 0, avg_seconds_per_review: null });
  const [sourceContentUrls, setSourceContentUrls] = useState([]);
  const [reviewData, setReviewData] = useState(null);

  useEffect(() => {
    fetchReviewStats(stateCode).then((res) => setStats(res.data)).catch(() => {});
  }, [stateCode]);

  const { data: wsMessage } = useWebSocket(userId ? `${MERGE_TOPIC_PREFIX}${userId}` : null, { autoConnect: !!userId });

  useEffect(() => {
    if (wsMessage?.type === MERGE_EVENT_ERROR) setError(wsMessage.error);
  }, [wsMessage]);

  const applyEntry = async (sessionData) => {
    const review = await fetchReview(sessionData.request_id).catch(() => null);
    setRequestId(sessionData.request_id);
    setJurisdiction(sessionData.jurisdiction);
    setPr(sessionData.pr);
    setPrPeople({ existing: sessionData.existing, proposed: sessionData.proposed });
    setEntryNumber(sessionData.entry_number);
    setFrontierEntry((prev) => Math.max(prev, sessionData.entry_number));
    setReviewData(review?.data ?? null);
    setSourceContentUrls(sessionData.sources);
    const status = sessionData.pr?.status;
    setIsReadOnly(status === "merged" || status === "closed");
    updateParams({ pull_request_number: sessionData.pr?.number != null ? String(sessionData.pr.number) : null });
  };

  const advance = async (sessionId?: string, targetEntry?: number) => {
    const sid = sessionId ?? session?.id;
    setIsNavigating(true);
    try {
      const target = targetEntry ?? entryNumber + 1;
      const res = await navigateToEntry(sid, target);
      const data = res?.data;
      if (!data) {
        onDone();
        return;
      }
      await applyEntry(data);
      onReviewing();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsNavigating(false);
    }
  };

  const back = async () => {
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
    try {
      await kickOffMerge(pr.number, requestId, jurisdiction.ocdid, people ?? null);
    } catch (err) {
      setError(err.message);
      return;
    }
    setResolvedEntryNumbers((prev) => new Set([...prev, entryNumber]));
    await advance();
  };

  const navigateTo = async (n) => {
    setIsNavigating(true);
    try {
      const res = await navigateToEntry(session?.id, n);
      const data = res?.data;
      if (!data) return;
      await applyEntry(data);
      onReviewing();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsNavigating(false);
    }
  };

  const initSession = (sessionId: string, dailyGoal: number, resolvedNumbers: number[], currentEntry: number) => {
    setSession({ id: sessionId, daily_goal: dailyGoal });
    setResolvedEntryNumbers(new Set(resolvedNumbers));
    setFrontierEntry(currentEntry);
  };

  const endSession = async () => {
    const sid = session?.id;
    if (sid) await endReviewSession(sid);
    setSession(null);
    setEntryNumber(0);
    setResolvedEntryNumbers(new Set());
    setFrontierEntry(0);
    updateParams({ pull_request_number: null });
    onIdle();
  };

  const [isReadOnly, setIsReadOnly] = useState(false);

  const loadDirectPr = async (prNumber: number): Promise<string | null> => {
    setIsNavigating(true);
    try {
      const res = await fetchPullRequestByNumber(prNumber);
      const data = res?.data;
      if (!data) return null;
      await applyEntry(data);
      const terminal = data.pr?.status === "merged" || data.pr?.status === "closed";
      setIsReadOnly(terminal);
      onReviewing();
      return data.jurisdiction?.ocdid ?? null;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setIsNavigating(false);
    }
  };

  return {
    session, setSession,
    jurisdiction,
    pr, requestId,
    progress: { entryNumber, hasPrev: entryNumber > 1, resolvedEntryNumbers, frontierEntry, isNavigating },
    prPeople,
    error, setError,
    stats,
    advance, back, endSession, merge, navigateTo, loadDirectPr, initSession,
    isReadOnly,
    sourceContentUrls, reviewData,
  };
}
