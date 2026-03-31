import { html } from "lit-html";
import { component, useState } from "haunted";
import "../../components/search-jurisdictions/select-state.js";
import "../../components/stat-cards/index.js";
import "../../components/streak-graph/streak-graph.js";

const MAX_PRESET_GOAL = 50;

function presetGoalOptions() {
  return Array.from({ length: MAX_PRESET_GOAL }, (_, i) => i + 1);
}

function ReviewLanding({ stateCode, stats, error, dailyGoal, effectiveGoal, onStateChange, onGoalChange, onStartReview }) {
  const [goalModalOpen, setGoalModalOpen] = useState(false);
  const [pendingGoal, setPendingGoal] = useState(dailyGoal);
  const [isCustomGoal, setIsCustomGoal] = useState(() => dailyGoal > MAX_PRESET_GOAL);

  return html`
    <main class="review-page">
      <div class="review-page__state-bar">
        <civ-select-state .selected=${stateCode} @state-change=${onStateChange}></civ-select-state>
      </div>
      <div class="review-page__main-grid">
        <div class="review-page__streak-card">
          <civ-streak-graph .dailyCounts=${stats.daily_counts ?? []} .streak=${stats.streak} .currentDate=${stats.current_date ?? null}></civ-streak-graph>
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
          <span class="review-page__ready-count">${Math.min(effectiveGoal, stats.available_count ?? 0)}</span>
          <span class="review-page__ready-sub">to review · ${stats.available_count} available in ${stateCode.toUpperCase()}</span>
          ${stats.today_resolved >= effectiveGoal ? html`
            <p class="review-page__goal-met">Daily goal of ${effectiveGoal} reached. Update via ⚙ to continue.</p>
          ` : ""}
${error ? html`<p class="review-page__error">${error}</p>` : ""}
          <button class="review-page__start-btn" @click=${onStartReview} ?disabled=${stats.today_resolved >= effectiveGoal || stats.available_count === 0}>Review →</button>
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
              ${presetGoalOptions().map((n) => html`<option value=${n}>${n}</option>`)}
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
