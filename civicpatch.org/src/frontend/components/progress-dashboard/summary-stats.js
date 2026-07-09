import { html } from "lit-html";
import { component } from "haunted";
import "../stat-cards/index.js";
import { computeStatusSegments, STATUS_LABELS } from "./status-segments.js";
import { dateStringToFriendly } from "../../utils/date-utils.js";

function percent(n, d) {
  if (!d || d === 0) return 0;
  return (n / d) * 100;
}

function percentLabel(n, d) {
  if (!d || d === 0) return "0%";
  return `${((n / d) * 100).toFixed(1)}%`;
}

function SummaryStats({ stats, state = "TX" }) {
  if (!stats || !stats.states || !stats.states[state]) return html``;
  const stateStats = stats.states[state];
  const {
    covered = 0,
    known = 1,
    scrapeable = 1,
  } = stateStats.civicpatch.localities;
  const { status_counts: statusCounts, cutoff } = stateStats.civicpatch;
  const segments = computeStatusSegments(statusCounts);

  const statsList = [
    {
      key: "reach",
      label: "Reach",
      value: percentLabel(covered, scrapeable),
      sub: `${covered} of ${scrapeable} jurisdictions`,
      copyText: `[coverage] ${percentLabel(covered, scrapeable)} (${covered} of ${scrapeable} jurisdictions)`,
      description:
        "Percentage of scrapeable jurisdictions covered by CivicPatch. A jurisdiction is scrapeable if it has a website we can crawl.",
    },
    {
      key: "total-coverage",
      label: "Total Coverage",
      value: percentLabel(covered, known),
      sub: `${covered} of ${known} jurisdictions`,
      copyText: `[total coverage] ${percentLabel(covered, known)} (${covered} of ${known} jurisdictions)`,
      description:
        "Percentage of all known jurisdictions covered, including those without scrapeable websites.",
    },
    {
      key: "officials",
      label: "Officials",
      value: stateStats.civicpatch.officials,
      copyText: `[officials] ${stateStats.civicpatch.officials}`,
      description: "Elected officials collected by CivicPatch for this state.",
    },
    {
      key: "localities",
      label: "Localities (all)",
      value: known,
      sub: `${scrapeable} scrapeable`,
      copyText: `[localities] ${known} total (${scrapeable} scrapeable)`,
      description:
        "Total known jurisdictions in the state. Scrapeable = those with websites we can target.",
    },
  ];

  return html`
    <style>
      .progress-bar-container {
        margin: 0 auto 2rem auto;
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
      }
      .progress-bar-container progress {
        width: 100%;
      }
      .progress-bar-container small {
        text-align: center;
        color: var(--pico-muted-color);
      }
      .status-segments-container {
        margin: 0 auto 0.5rem auto;
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
      }
      .status-segments-container__header {
        display: flex;
        justify-content: flex-end;
        font-size: var(--text-xs);
        color: var(--pico-muted-color);
      }
      .status-segments-bar {
        display: flex;
        width: 100%;
        height: 0.5rem;
        border-radius: 999px;
        overflow: hidden;
        background: var(--civ-surface-2);
      }
      .status-segments-bar__segment {
        height: 100%;
        transition: width 200ms ease;
      }
      .status-segments-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        justify-content: center;
      }
      .status-segments-legend__item {
        display: flex;
        align-items: center;
        gap: 0.3rem;
        font-size: var(--text-xs);
        color: var(--pico-muted-color);
      }
      .status-segments-legend__dot {
        width: 0.5rem;
        height: 0.5rem;
        border-radius: 50%;
      }
      .status-segments-legend__count {
        font-weight: 700;
        color: var(--pico-color);
      }
    </style>
    <section>
      <div
        class="progress-bar-container"
        title="Total Coverage: ${covered} of ${known} known localities"
      >
        <progress value="${covered}" max="${scrapeable}"></progress>
        <small>${percentLabel(covered, scrapeable)} covered</small>
      </div>
      <div class="status-segments-container">
        ${cutoff
          ? html`<div class="status-segments-container__header">
              Data fresh after ${dateStringToFriendly(cutoff)}
            </div>`
          : ""}
        <div class="status-segments-bar">
          ${segments.map(
            (s) => html`<div
              class="status-segments-bar__segment"
              style="width:${s.percent}%; background:var(--civ-status-${s.key})"
              title="${STATUS_LABELS[s.key]}: ${s.count}"
            ></div>`,
          )}
        </div>
        <div class="status-segments-legend">
          ${segments.map(
            (s) => html`<span class="status-segments-legend__item">
              <span
                class="status-segments-legend__dot"
                style="background:var(--civ-status-${s.key})"
              ></span>
              <span class="status-segments-legend__count">${s.count}</span>
              ${STATUS_LABELS[s.key]}
            </span>`,
          )}
        </div>
      </div>
      <stat-cards .stats=${statsList}></stat-cards>
    </section>
  `;
}

customElements.define(
  "summary-stats",
  component(SummaryStats, { useShadowDOM: false }),
);
export default SummaryStats;
