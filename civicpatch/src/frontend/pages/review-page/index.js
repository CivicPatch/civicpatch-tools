import { html } from "lit-html";
import { component, useState } from "haunted";
import { createReviewSession } from "../../api.js";
import "../../components/pull-request-card/index.js";
import "../../components/search-jurisdictions/select-state.js";
import "../../components/stat-cards/index.js";
import { useReviewSession, updateParams } from "./use-review-session.js";

const DEFAULT_STATE_KEY = "review_state_code";
const DEFAULT_GOAL_KEY = "review_daily_goal";
const DEFAULT_STATE = "tx";
const DEFAULT_GOAL = 10;
const MAX_PRESET_GOAL = 50;

function presetGoalOptions() {
  return Array.from({ length: MAX_PRESET_GOAL }, (_, i) => i + 1);
}

const PAGE_STATE = {
  LOADING: "loading",
  IDLE: "idle",
  REVIEWING: "reviewing",
};

function getInitialStateCode() {
  const p = new URLSearchParams(window.location.search);
  return p.get("state") || localStorage.getItem(DEFAULT_STATE_KEY) || DEFAULT_STATE;
}

function ReviewPage() {
  const [pageState, setPageState] = useState(PAGE_STATE.LOADING);
  const [stateCode, setStateCode] = useState(getInitialStateCode);
  const [dailyGoal, setDailyGoal] = useState(
    parseInt(localStorage.getItem(DEFAULT_GOAL_KEY), 10) || DEFAULT_GOAL
  );
  const [goalModalOpen, setGoalModalOpen] = useState(false);
  const [pendingGoal, setPendingGoal] = useState(dailyGoal);
  const [isCustomGoal, setIsCustomGoal] = useState(() => dailyGoal > MAX_PRESET_GOAL);

  const {
    session, setSession,
    currentJob, currentPeople,
    entryNumber, resolvedCount,
    hasNext,
    prState, error, setError,
    stats,
    advance, back, pass, pause, merge, close, navigateTo,
    passedEntryNumbers, resolvedEntryNumbers, frontierEntry,
  } = useReviewSession(stateCode, {
    onReviewing: () => setPageState(PAGE_STATE.REVIEWING),
    onDone: () => setPageState(PAGE_STATE.IDLE),
    onIdle: () => setPageState(PAGE_STATE.IDLE),
  });

  const handleStateChange = (e) => {
    const newState = e.detail.state;
    setStateCode(newState);
    localStorage.setItem(DEFAULT_STATE_KEY, newState);
    updateParams({ state: newState, session: null, request: null });
  };

  const handleSelectGoal = (n) => {
    const clamped = stats.available_count > 0 ? Math.min(n, stats.available_count) : n;
    setDailyGoal(clamped);
    localStorage.setItem(DEFAULT_GOAL_KEY, String(clamped));
  };

  const effectiveGoal = stats.available_count > 0 ? Math.min(dailyGoal, stats.available_count) : dailyGoal;

  const handleStartReview = async () => {
    setPageState(PAGE_STATE.LOADING);
    setError(null);
    try {
      const sessionRes = await createReviewSession(stateCode, effectiveGoal);
      const newSession = sessionRes.data;
      setSession(newSession);
      updateParams({ state: stateCode, session: newSession.id, request: null });
      await advance(newSession.id);
    } catch (err) {
      setError(err.message);
      setPageState(PAGE_STATE.IDLE);
    }
  };

  if (pageState === PAGE_STATE.LOADING) {
    return html`<main class="review-page"><p>Loading...</p></main>`;
  }

  if (pageState === PAGE_STATE.IDLE) {
    return html`
      <main class="review-page">
        <div class="review-page__state-bar">
          <civ-select-state .selected=${stateCode} @state-change=${handleStateChange}></civ-select-state>
        </div>
        <div class="review-page__main-grid">
          <div class="review-page__streak-card">
            <span class="review-page__streak-label">Day Streak</span>
            <span class="review-page__streak-value">${stats.streak}</span>
            <span class="review-page__streak-sub">${stats.streak === 1 ? "day" : "days"}</span>
          </div>
          <div class="review-page__ready-card">
            <div class="review-page__ready-header">
              <span class="review-page__ready-title">Ready for Review</span>
              <div class="review-page__goal-control">
                <button class="review-page__gear-btn" @click=${() => {
                  setPendingGoal(dailyGoal);
                  setIsCustomGoal(true);
                  setGoalModalOpen(true);
                }}>
                  <i class="fa-solid fa-gear"></i>
                </button>
                <span class="review-page__goal-label">Goal: ${dailyGoal}</span>
              </div>
            </div>
            <span class="review-page__ready-count">${effectiveGoal}</span>
            <span class="review-page__ready-sub">reviews today · ${stats.available_count} available in ${stateCode.toUpperCase()}</span>
            ${stats.today_resolved >= effectiveGoal ? html`
              <p class="review-page__goal-met">Daily goal of ${effectiveGoal} reached. Update via ⚙ to continue.</p>
            ` : ""}
            ${error ? html`<p class="review-page__error">${error}</p>` : ""}
            <button class="review-page__start-btn" @click=${handleStartReview} ?disabled=${stats.today_resolved >= effectiveGoal}>Review →</button>
          </div>
        </div>
        <stat-cards class="review-page__stat-cards" .stats=${[
          { key: "today", label: "Today", value: stats.today_resolved, sub: "reviews" },
          { key: "all_time", label: "All time", value: stats.all_time_resolved, sub: "reviews" },
        ]}></stat-cards>
        ${goalModalOpen ? html`
          <div class="review-page__modal-backdrop" @click=${() => setGoalModalOpen(false)}>
            <div class="review-page__modal" @click=${(e) => e.stopPropagation()}>
              <div class="review-page__modal-header">
                <span>Daily Goal</span>
                <button class="modal-close" @click=${() => setGoalModalOpen(false)}>✕</button>
              </div>
              <select
                .value=${isCustomGoal ? "custom" : String(pendingGoal)}
                @change=${(e) => {
                  if (e.target.value === "custom") {
                    setIsCustomGoal(true);
                  } else {
                    setIsCustomGoal(false);
                    setPendingGoal(parseInt(e.target.value, 10));
                  }
                }}
              >
                ${presetGoalOptions().map((n) => html`
                  <option value=${n}>${n}</option>
                `)}
                <option value="custom">Custom…</option>
              </select>
              ${isCustomGoal ? html`
                <input
                  type="number"
                  min="1"
                  .value=${String(pendingGoal)}
                  @input=${(e) => setPendingGoal(parseInt(e.target.value, 10) || 1)}
                />
              ` : ""}
              <button class="review-page__modal-save" @click=${() => {
                handleSelectGoal(pendingGoal);
                setGoalModalOpen(false);
              }}>Save</button>
            </div>
          </div>
        ` : ""}
      </main>
    `;
  }

  // REVIEWING
  const goal = session.daily_goal;
  const displayMax = hasNext ? goal : entryNumber;
  const progressPct = Math.min(100, Math.round((resolvedCount / goal) * 100));

  const getDotStatus = (n) => {
    if (n === entryNumber) return "current";
    if (resolvedEntryNumbers.has(n)) return "resolved";
    if (passedEntryNumbers.has(n)) return "passed";
    if (n <= frontierEntry) return "deferred";
    return "future";
  };
  const debug_state = {
    server: {
      session,
      current_job: currentJob,
      current_people: currentPeople ? { existing: currentPeople.existing?.length, pull_request: currentPeople.pull_request?.length } : null,
      entry_number: entryNumber,
      resolved_count: resolvedCount,
      stats,
    },
    client: {
      page_state: pageState,
      state_code: stateCode,
      daily_goal: dailyGoal,
      goal_modal_open: goalModalOpen,
      pending_goal: pendingGoal,
      is_custom_goal: isCustomGoal,
      has_next: hasNext,
      pr_state: prState,
      error,
      goal,
      progress_pct: progressPct,
    },
  };

  return html`
    <main class="review-page" @onMerge=${merge} @onClose=${close}>
      <div class="review-page__dots">
        ${Array.from({ length: goal }, (_, i) => i + 1).map((n) => {
          const status = getDotStatus(n);
          return html`<button
            class="review-page__dot review-page__dot--${status}"
            ?disabled=${status === "future" || status === "current"}
            @click=${() => navigateTo(n)}
          ></button>`;
        })}
      </div>
      <div class="review-page__toolbar">
        <button class="btn-sm review-page__back-btn" @click=${back} ?disabled=${entryNumber <= 1}>← Back</button>
        <button class="btn-sm review-page__pass-btn" @click=${pass} ?disabled=${!hasNext}>Pass</button>
        <button class="btn-sm" @click=${() => advance()} ?disabled=${!hasNext || entryNumber >= goal}>Next →</button>
      </div>
      <span class="review-page__progress">${entryNumber} of ${displayMax}</span>
      ${error ? html`<p class="review-page__error">${error}</p>` : ""}
      <pr-card
        .pr=${currentJob}
        .data=${currentPeople}
        .state=${prState}
      ></pr-card>
      <pre style="font-size:0.75rem;opacity:0.6;overflow:auto">${JSON.stringify(debug_state, null, 2)}</pre>
      <button class="review-page__end-btn" @click=${pause}>End session</button>
    </main>
  `;
}

customElements.define("review-page", component(ReviewPage, { useShadowDOM: false }));
