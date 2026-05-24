import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { createReviewSession, navigateToEntry, fetchReviewStats, fetchActiveReviewSession } from "../../api.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { sessionUrl, STATE_PARAM } from "../review-routes.js";
import { DEFAULT_STATS } from "../review-session-page/review-state.js";
import "./review-landing.js";
import "./review-page.css";

const DEFAULT_STATE_KEY = "app:default-state";
const DEFAULT_GOAL_KEY = "review_daily_goal";
const DEFAULT_GOAL = 10;

function getStateFromUrl() {
  return (new URLSearchParams(window.location.search).get(STATE_PARAM) || "").toLowerCase();
}

function ReviewPage() {
  const [defaultState] = useLocalStorage(DEFAULT_STATE_KEY, "");
  const stateCode = (getStateFromUrl() || defaultState || "").toLowerCase();
  const [dailyGoal, setDailyGoal] = useLocalStorage(DEFAULT_GOAL_KEY, DEFAULT_GOAL, { ttl: PERSIST_FOREVER });

  const [stats, setStats] = useState(DEFAULT_STATS);
  const [error, setError] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const resumable = activeSession != null;

  useEffect(() => {
    fetchReviewStats(stateCode).then((res) => setStats(res.data)).catch(() => {});
    fetchActiveReviewSession(stateCode).then((res) => setActiveSession(res.data)).catch(() => {});
  }, [stateCode]);

  // Cap at total reviewable today (already-resolved + still-available), not just remaining;
  // never below what's already claimed.
  const maxReviewable = (stats.today_resolved ?? 0) + (stats.available_count ?? 0);
  const effectiveGoal = Math.max(
    maxReviewable > 0 ? Math.min(dailyGoal, maxReviewable) : dailyGoal,
    stats.claimed_count ?? 0,
  );

  const handleGoalChange = (n) => {
    const clamped = maxReviewable > 0 ? Math.min(n, maxReviewable) : n;
    setDailyGoal(clamped);
  };

  // With an active session, just hand off to the session route, which resumes
  // it. Otherwise create the session, claim its first entry, then hand off.
  const handleStartReview = async () => {
    if (resumable) {
      window.location.href = sessionUrl(stateCode);
      return;
    }
    setError(null);
    try {
      const session = (await createReviewSession(stateCode, effectiveGoal)).data;
      await navigateToEntry(session.id, session.next_entry_number);
      window.location.href = sessionUrl(stateCode);
    } catch (err) {
      setError(err.message);
    }
  };

  return html`<review-landing
    .stateCode=${stateCode}
    .stats=${stats}
    .error=${error}
    .dailyGoal=${dailyGoal}
    .effectiveGoal=${effectiveGoal}
    .resumable=${resumable}
    .onGoalChange=${handleGoalChange}
    .onStartReview=${handleStartReview}
  ></review-landing>`;
}

customElements.define("review-page", component(ReviewPage, { useShadowDOM: false }));
