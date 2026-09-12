import { html } from "lit-html";
import { component, useState, useEffect } from "haunted";
import { createReviewSession, navigateToEntry, fetchReviewStats, fetchActiveReviewSession, fetchAvailableReviewStates } from "../../api.js";
import { useLocalStorage, PERSIST_FOREVER } from "../../hooks/use-local-storage.js";
import { STORAGE_KEYS } from "../../utils/storage-keys.js";
import { landingUrl, sessionUrl, STATE_PARAM } from "../review-routes.js";
import { DEFAULT_STATS } from "../review-session-page/review-state.js";
import { SESSION_COUNTS } from "./review-landing.js";
import "../../components/panel/panel.css";
import "./review-page.css";

function getStateFromUrl() {
  return (new URLSearchParams(window.location.search).get(STATE_PARAM) || "").toLowerCase();
}

function ReviewPage() {
  const [defaultState, setDefaultState] = useLocalStorage(STORAGE_KEYS.DEFAULT_STATE, "", { ttl: PERSIST_FOREVER });
  const stateCode = (getStateFromUrl() || defaultState || "").toLowerCase();
  // Not persisted — the backend already remembers the length from this user's last
  // session (create_or_get_review_session falls back to it when none is passed), so
  // caching a second copy here would just be a weaker, device-scoped duplicate of
  // that. This is only what the reader has explicitly picked in this page view.
  const [chosenCount, setChosenCount] = useState<number | undefined>(undefined);

  const [stats, setStats] = useState(DEFAULT_STATS);
  const [error, setError] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const [availableStates, setAvailableStates] = useState([]);
  const resumable = activeSession != null;

  useEffect(() => {
    if (!stateCode) return;
    fetchReviewStats(stateCode).then((res) => setStats(res.data)).catch(() => {});
    fetchActiveReviewSession(stateCode).then((res) => setActiveSession(res.data)).catch(() => {});
  }, [stateCode]);

  // Fetched unconditionally, not just when no state is picked yet — the landing
  // page also offers this list as a switcher once a state is already chosen.
  useEffect(() => {
    fetchAvailableReviewStates().then((res) => setAvailableStates(res.data)).catch(() => {});
  }, []);

  const handlePickState = (code) => {
    setDefaultState(code);
    window.location.href = landingUrl(code);
  };

  // What can actually be picked (and submitted) is capped to what's available right
  // now, same as the picker's own disabled options. No explicit pick yet, or the
  // picked one is no longer valid, falls back to the smallest valid option — always
  // a concrete, visible value, since whatever the picker highlights is exactly what
  // gets submitted, never a different number silently substituted underneath it.
  const validCounts = SESSION_COUNTS.filter((n) => n <= (stats.available_count ?? 0));
  const sessionCount =
    chosenCount !== undefined && validCounts.includes(chosenCount)
      ? chosenCount
      : (validCounts[0] ?? chosenCount);

  const handleSessionCountChange = (n) => {
    setChosenCount(n);
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
      const session = (await createReviewSession(stateCode, sessionCount)).data;
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
    .sessionCount=${sessionCount}
    .resumable=${resumable}
    .availableStates=${availableStates}
    .onSessionCountChange=${handleSessionCountChange}
    .onStartReview=${handleStartReview}
    .onPickState=${handlePickState}
  ></review-landing>`;
}

customElements.define("review-page", component(ReviewPage, { useShadowDOM: false }));
