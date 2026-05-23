import { html } from "lit-html";
import { component } from "haunted";
import "../stat-cards/index.js";

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
    coverage = 0,
    known = 1,
    scrapeable = 1,
  } = stateStats.civicpatch.localities;

  const statsList = [
    {
      key: "reach",
      label: "Reach",
      value: percentLabel(coverage, scrapeable),
      sub: `${coverage} of ${scrapeable} jurisdictions`,
      copyText: `[coverage] ${percentLabel(coverage, scrapeable)} (${coverage} of ${scrapeable} jurisdictions)`,
      description:
        "Percentage of scrapeable jurisdictions covered by CivicPatch. A jurisdiction is scrapeable if it has a website we can crawl.",
    },
    {
      key: "total-coverage",
      label: "Total Coverage",
      value: percentLabel(coverage, known),
      sub: `${coverage} of ${known} jurisdictions`,
      copyText: `[total coverage] ${percentLabel(coverage, known)} (${coverage} of ${known} jurisdictions)`,
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
    </style>
    <section>
      <div
        class="progress-bar-container"
        title="Total Coverage: ${coverage} of ${known} known localities"
      >
        <progress value="${coverage}" max="${scrapeable}"></progress>
        <small>${percentLabel(coverage, scrapeable)} covered</small>
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
