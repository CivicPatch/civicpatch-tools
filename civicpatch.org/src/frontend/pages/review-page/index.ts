import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { createReviewSession, navigateToEntry, fetchReviewStats, fetchActiveReviewSession } from "../../api.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { STORAGE_KEYS } from "../../utils/storage-keys.js";
import { sessionUrl, STATE_PARAM, DEFAULT_DAILY_GOAL } from "../review-routes.js";
import { DEFAULT_STATS } from "../review-session-page/review-state.js";
import "./review-landing.js";
import "./review-page.css";

function getStateFromUrl() {
  return (new URLSearchParams(window.location.search).get(STATE_PARAM) || "").toLowerCase();
}

function ReviewPage() {
  const [defaultState] = useLocalStorage(STORAGE_KEYS.DEFAULT_STATE, "", { ttl: PERSIST_FOREVER });
  const stateCode = (getStateFromUrl() || defaultState || "").toLowerCase();
  const [dailyGoal, setDailyGoal] = useLocalStorage(STORAGE_KEYS.DAILY_GOAL, DEFAULT_DAILY_GOAL, { ttl: PERSIST_FOREVER });

  const [stats, setStats] = useState(DEFAULT_STATS);
  const [error, setError] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const resumable = activeSession != null;

  useEffect(() => {
    fetchReviewStats(stateCode).then((res) => setStats(res.data)).catch(() => {});
    fetchActiveReviewSession(stateCode).then((res) => setActiveSession(res.data)).catch(() => {});
  }, [stateCode]);

  // The goal is the user's chosen target — never clamped to availability or
  // progress. A session simply ends early if there aren't enough cards to reach it.
  const effectiveGoal = dailyGoal;

  const handleGoalChange = (n) => {
    setDailyGoal(n);
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
