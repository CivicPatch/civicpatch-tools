import { useState, useEffect } from "haunted";
import {
  fetchReviewStats,
  fetchReview,
  fetchPullRequestByNumber,
  endReviewSession,
  navigateToEntry,
} from "../../api.js";

export function updateParams(updates: Record<string, string | null | undefined>) {
  const p = new URLSearchParams(window.location.search);
  for (const [k, v] of Object.entries(updates)) {
    if (v == null) p.delete(k);
    else p.set(k, v);
  }
  history.replaceState(null, "", `?${p}`);
}

type OnMerge = (
  pullRequestNumber: number,
  requestId: string,
  jurisdictionOcdid: string,
  people: any[] | null,
  jurisdictionName: string,
) => Promise<void>;

// The data for the entry currently displayed in the review card. Keys are
// snake_case because this object crosses module boundaries (hook → page →
// review-session component), matching the API contract — see CLAUDE.md.
export type CurrentEntry = {
  request_id: string;
  jurisdiction: { ocdid: string | null; name: string | null; path?: string | null };
  pr: { url: string | null; status: string | null; reviewState: string | null; number?: number | null };
  pr_people: { existing: any[]; proposed: any[] };
  review_data: any;
  source_content_urls: any[];
  is_read_only: boolean;
  has_next: boolean;
};

export function useReviewSession(stateCode, { onReviewing, onDone, onIdle, onMerge }: {
  onReviewing: () => void;
  onDone: () => void;
  onIdle: () => void;
  onMerge: OnMerge;
}) {
  const [session, setSession] = useState<{ id: string; daily_goal: number } | null>(null);
  const [currentEntry, setCurrentEntry] = useState<CurrentEntry | null>(null);
  const [entryNumber, setEntryNumber] = useState(0);
  const [isNavigating, setIsNavigating] = useState(false);
  const [resolvedEntryNumbers, setResolvedEntryNumbers] = useState(new Set());
  const [frontierEntry, setFrontierEntry] = useState(0);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState({ today_resolved: 0, streak: 0, all_time_resolved: 0, available_count: 0, claimed_count: 0, best_streak: 0, avg_seconds_per_review: null });

  useEffect(() => {
    fetchReviewStats(stateCode).then((res) => setStats(res.data)).catch(() => {});
  }, [stateCode]);

  const applyEntry = async (sessionData) => {
    const review = await fetchReview(sessionData.request_id).catch(() => null);
    const status = sessionData.pr?.status;
    setCurrentEntry({
      request_id: sessionData.request_id,
      jurisdiction: sessionData.jurisdiction,
      pr: sessionData.pr,
      pr_people: { existing: sessionData.existing, proposed: sessionData.proposed },
      review_data: review?.data ?? null,
      source_content_urls: sessionData.sources,
      is_read_only: status === "merged" || status === "closed",
      has_next: sessionData.has_next ?? false,
    });
    setEntryNumber(sessionData.entry_number);
    setFrontierEntry((prev) => Math.max(prev, sessionData.entry_number));
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
    if (!currentEntry?.pr?.number || !currentEntry?.request_id) return;
    const { pr, request_id, jurisdiction } = currentEntry;
    onMerge(pr.number!, request_id, jurisdiction.ocdid!, people ?? null, jurisdiction.name ?? `#${pr.number}`);
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

  const initSession = (sessionId: string, dailyGoal: number, resolvedNumbers: number[], currentEntryNumber: number) => {
    setSession({ id: sessionId, daily_goal: dailyGoal });
    setResolvedEntryNumbers(new Set(resolvedNumbers));
    setFrontierEntry(currentEntryNumber);
    setEntryNumber(currentEntryNumber);
  };

  // Drops in-memory session/card state and returns to idle. Does NOT touch the
  // DB session — used when the user switches navbar state so the old state's
  // DB session stays alive and is resumable.
  const resetLocalSession = () => {
    setSession(null);
    setCurrentEntry(null);
    setEntryNumber(0);
    setResolvedEntryNumbers(new Set());
    setFrontierEntry(0);
    updateParams({ pull_request_number: null });
    onIdle();
  };

  const endSession = async () => {
    const sid = session?.id;
    if (sid) await endReviewSession(sid).catch(() => {});
    resetLocalSession();
  };

  const loadDirectPr = async (prNumber: number): Promise<boolean> => {
    setIsNavigating(true);
    try {
      const res = await fetchPullRequestByNumber(prNumber);
      const data = res?.data;
      if (!data) return false;
      await applyEntry(data);
      onReviewing();
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setIsNavigating(false);
    }
  };

  return {
    session, setSession,
    currentEntry,
    progress: { entryNumber, hasPrev: entryNumber > 1, resolvedEntryNumbers, frontierEntry, isNavigating },
    error, setError,
    stats,
    advance, back, endSession, resetLocalSession, merge, navigateTo, loadDirectPr, initSession,
  };
}
