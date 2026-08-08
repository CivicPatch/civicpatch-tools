import { useEffect, useState } from "haunted";
import { fetchActiveReviewSession, fetchReviewStats } from "../../api.js";

// Both endpoints are AUTHENTICATED routes, so anonymous visitors — the common case —
// skip them entirely rather than firing calls that will 401.
export function useReviewProgress(user: unknown, selectedState: string) {
  const [reviewStats, setReviewStats] = useState<any>(null);
  const [activeSession, setActiveSession] = useState<any>(null);

  useEffect(() => {
    if (!user || !selectedState) {
      setReviewStats(null);
      setActiveSession(null);
      return;
    }
    fetchReviewStats(selectedState)
      .then((d: any) => setReviewStats(d.data ?? null))
      .catch(() => setReviewStats(null));
    fetchActiveReviewSession(selectedState)
      .then((d: any) => setActiveSession(d.data ?? null))
      .catch(() => setActiveSession(null));
  }, [user, selectedState]);

  return { reviewStats, activeSession };
}
