import { html } from "lit-html";
import { component } from "haunted";
import "../../components/stat-cards/index.js";
import "../../components/streak-graph/streak-graph.js";
import {
  LEADERBOARD_PERIOD_WEEK,
  LEADERBOARD_PERIOD_ALL_TIME,
} from "../../components/leaderboard/index.js";

function formatDuration(seconds) {
  if (seconds == null) return "—";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function formatDate(iso) {
  return new Date(iso).toLocaleString();
}

export const SESSION_COUNTS = [5, 10, 25, 50];

function ReviewLanding({
  stateCode,
  stats,
  error,
  sessionCount,
  resumable,
  availableStates,
  onSessionCountChange,
  onStartReview,
  onPickState,
}) {
  const available = stats.available_count ?? 0;
  const canStart = resumable || (stateCode && available > 0);
  return html`
    <main class="review-page review-page--narrow">
      <div class="page-focal">
        <h1 class="page-focal__title">Overview</h1>
      </div>
      <div class="review-page__layout">
        <div class="review-page__main">
          <div class="panel review-page__ready-card">
            <div class="panel__cap"><b>Ready for Review</b></div>
            ${availableStates.length
              ? html`
                  <div class="review-page__state-chips">
                    ${availableStates.map(
                      (s) => html`
                        <button
                          class="review-page__state-chip ${s.state_code ===
                          stateCode
                            ? "review-page__state-chip--active"
                            : ""}"
                          @click=${() => onPickState(s.state_code)}
                        >
                          <span class="review-page__state-chip-name"
                            >${s.state_name}</span
                          >
                          <span class="review-page__state-chip-count"
                            >${s.available_count}</span
                          >
                        </button>
                      `,
                    )}
                  </div>
                `
              : ""}
            ${!stateCode
              ? html`
                  <div class="review-page__ready-empty">
                    <i class="fa-solid fa-location-dot"></i>
                    <span class="review-page__ready-empty-title"
                      >${availableStates.length
                        ? "Pick a state above to begin"
                        : "Nothing to review"}</span
                    >
                    ${availableStates.length
                      ? ""
                      : html`<span
                          >Nothing is waiting for review anywhere right
                          now.</span
                        >`}
                  </div>
                `
              : html`
                  <span class="review-page__ready-count">${available}</span>
                  <span class="review-page__ready-sub"
                    >${available
                      ? `available in ${stateCode.toUpperCase()}`
                      : `nothing waiting in ${stateCode.toUpperCase()}`}</span
                  >
                  ${error
                    ? html`<p class="review-page__error">${error}</p>`
                    : ""}
                  <div class="review-page__goal-chips">
                    ${SESSION_COUNTS.map(
                      (n) => html`
                        <button
                          class="review-page__goal-chip ${n === sessionCount
                            ? "review-page__goal-chip--active"
                            : ""}"
                          ?disabled=${n > available}
                          @click=${() => onSessionCountChange(n)}
                        >
                          ${n}
                        </button>
                      `,
                    )}
                  </div>
                  <button
                    class="review-page__start-btn btn-gradient"
                    @click=${onStartReview}
                    ?disabled=${!canStart}
                  >
                    ${resumable ? "Resume" : "Review"}
                    <i class="fa-solid fa-arrow-right"></i>
                  </button>
                `}
          </div>
          <div class="panel review-page__recent-card">
            <div class="panel__cap"><b>Your Recent Activity</b></div>
            ${stats.recent_activity?.length
              ? html`
                  <div class="review-page__recent-list">
                    ${stats.recent_activity.map(
                      (entry) => html`
                        <div class="review-page__recent-row">
                          <span class="review-page__recent-summary"
                            >${entry.summary}</span
                          >
                          <span class="review-page__recent-meta">
                            ${entry.jurisdiction_name
                              ? html`<span>${entry.jurisdiction_name}</span>`
                              : ""}
                            <span data-visual-volatile
                              >${formatDate(entry.created_at)}</span
                            >
                          </span>
                        </div>
                      `,
                    )}
                  </div>
                `
              : html`<p class="review-page__recent-empty">
                  Nothing published yet.
                </p>`}
          </div>
        </div>
        <div class="review-page__sidebar">
          <div class="panel review-page__streak-card">
            <civ-streak-graph
              .dailyCounts=${stats.daily_counts ?? []}
              .streak=${stats.streak}
              .currentDate=${stats.current_date ?? null}
            ></civ-streak-graph>
          </div>
          <stat-cards
            class="review-page__stat-cards"
            .stats=${[
              {
                key: "today",
                label: "Today",
                value: stats.today_resolved,
                sub: "reviews",
              },
              {
                key: "all_time",
                label: "All time",
                value: stats.all_time_resolved,
                sub: "reviews",
              },
              {
                key: "best_streak",
                label: "Best streak",
                value: stats.best_streak ?? 0,
                sub: "days",
              },
              {
                key: "avg_time",
                label: "Avg time",
                value: formatDuration(stats.avg_seconds_per_review),
                sub: "per review (30d)",
              },
            ]}
          ></stat-cards>
          <div class="panel review-page__leaderboard-card">
            <civ-leaderboard
              title="This Week"
              period=${LEADERBOARD_PERIOD_WEEK}
            ></civ-leaderboard>
          </div>
          <div class="panel review-page__leaderboard-card">
            <civ-leaderboard
              title="All Time"
              period=${LEADERBOARD_PERIOD_ALL_TIME}
            ></civ-leaderboard>
          </div>
        </div>
      </div>
    </main>
  `;
}

customElements.define(
  "review-landing",
  component(ReviewLanding, { useShadowDOM: false }),
);
