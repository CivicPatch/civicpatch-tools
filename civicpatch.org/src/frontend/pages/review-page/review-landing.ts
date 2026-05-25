import { html } from "lit-html";
import { component, useState } from "haunted";
import { reviewsReady } from "../review-session-page/review-progress.js";
import "../../components/stat-cards/index.js";
import "../../components/streak-graph/streak-graph.js";
import "../../components/goal-ring/goal-ring.js";

function formatDuration(seconds) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function ReviewLanding({ stateCode, stats, error, dailyGoal, effectiveGoal, resumable, onGoalChange, onStartReview }) {
  const [goalModalOpen, setGoalModalOpen] = useState(false);
  const [pendingGoal, setPendingGoal] = useState(dailyGoal);

  // Resume is always available; a fresh review needs a state, an unmet goal, and something to review.
  const canStart = resumable || (stateCode && stats.today_resolved < effectiveGoal && stats.available_count > 0);

  return html`
    <main class="review-page">
      <div class="review-page__main-grid">
        <div class="review-page__streak-card">
          <civ-streak-graph .dailyCounts=${stats.daily_counts ?? []} .streak=${stats.streak} .currentDate=${stats.current_date ?? null}></civ-streak-graph>
        </div>
        <div class="review-page__ready-card">
          <div class="review-page__ready-header">
            <span class="review-page__ready-title">Ready for Review</span>
            ${stateCode ? html`
            <div class="review-page__goal-control">
              <button class="review-page__gear-btn btn-icon" @click=${() => {
                setPendingGoal(dailyGoal);
                setGoalModalOpen(true);
              }}>
                <i class="fa-solid fa-gear"></i>
              </button>
              <span class="review-page__goal-label">Goal: ${dailyGoal}</span>
            </div>
            ` : ""}
          </div>
          ${!stateCode ? html`
            <div class="review-page__ready-empty">
              <i class="fa-solid fa-location-dot"></i>
              <span class="review-page__ready-empty-title">Pick a state to begin</span>
              <span>Use the state selector in the top nav to load reviews.</span>
            </div>
          ` : html`
            <span class="review-page__ready-count">${reviewsReady(stats.available_count ?? 0, dailyGoal, stats.today_resolved ?? 0)}</span>
            <civ-goal-ring .resolved=${stats.today_resolved} .goal=${dailyGoal}></civ-goal-ring>
            <span class="review-page__ready-sub">to review · ${stats.available_count} available in ${stateCode.toUpperCase()}</span>
            ${stats.today_resolved >= effectiveGoal ? html`
              <p class="review-page__goal-met">Daily goal of ${effectiveGoal} reached. Update via ⚙ to continue.</p>
            ` : ""}
            ${error ? html`<p class="review-page__error">${error}</p>` : ""}
            <button class="review-page__start-btn btn-gradient" @click=${onStartReview} ?disabled=${!canStart}>${resumable ? "Resume" : "Review"} <i class="fa-solid fa-arrow-right"></i></button>
          `}
        </div>
      </div>
      <stat-cards class="review-page__stat-cards" .stats=${[
        { key: "today", label: "Today", value: stats.today_resolved, sub: "reviews" },
        { key: "all_time", label: "All time", value: stats.all_time_resolved, sub: "reviews" },
        { key: "best_streak", label: "Best streak", value: stats.best_streak ?? 0, sub: "days" },
        { key: "avg_time", label: "Avg time", value: formatDuration(stats.avg_seconds_per_review), sub: "per review (30d)" },
      ]}></stat-cards>
      ${goalModalOpen ? html`
        <div class="review-page__modal-backdrop" @click=${() => setGoalModalOpen(false)}>
          <div class="review-page__modal" @click=${(e) => e.stopPropagation()}>
            <div class="review-page__modal-header">
              <span>Daily Goal</span>
              <button class="modal-close" @click=${() => setGoalModalOpen(false)}>✕</button>
            </div>
            <input
              type="number"
              min="1"
              .value=${String(pendingGoal)}
              @input=${(e) => setPendingGoal(parseInt(e.target.value, 10) || 1)}
            />
            <button class="review-page__modal-save" @click=${() => {
              onGoalChange(pendingGoal);
              setGoalModalOpen(false);
            }}>Save</button>
          </div>
        </div>
      ` : ""}
    </main>
  `;
}

customElements.define("review-landing", component(ReviewLanding, { useShadowDOM: false }));
