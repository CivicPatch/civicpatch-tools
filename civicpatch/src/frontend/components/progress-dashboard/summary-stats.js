import { html } from 'lit-html';
import { component } from 'haunted';
import '../stat-cards/index.js';

function percent(n, d) {
  if (!d || d === 0) return 0;
  return ((n / d) * 100);
}

function percentLabel(n, d) {
  if (!d || d === 0) return '0%';
  return `${((n / d) * 100).toFixed(1)}%`;
}

function SummaryStats({ stats, state = 'TX' }) {
  if (!stats || !stats.states || !stats.states[state]) return html``;
  const stateStats = stats.states[state];
  const { coverage = 0, known = 1, scrapeable = 1, coverage_since_coverage_reference_date = 0 } = stateStats.civicpatch.localities;

  const actualCoverage = coverage_since_coverage_reference_date || coverage;

  const statsList = [
    {
      key: 'coverage',
      label: 'Coverage',
      value: percentLabel(actualCoverage, scrapeable),
      sub: `${actualCoverage} of ${scrapeable} jurisdictions`,
      copyText: `[coverage] ${percentLabel(actualCoverage, scrapeable)} (${actualCoverage} of ${scrapeable} jurisdictions)`,
      description: 'Percentage of scrapeable jurisdictions covered by CivicPatch. A jurisdiction is scrapeable if it has a website we can crawl.',
    },
    {
      key: 'total-coverage',
      label: 'Total Coverage',
      value: percentLabel(actualCoverage, known),
      sub: `${actualCoverage} of ${known} jurisdictions`,
      copyText: `[total coverage] ${percentLabel(actualCoverage, known)} (${actualCoverage} of ${known} jurisdictions)`,
      description: 'Percentage of all known jurisdictions covered, including those without scrapeable websites.',
    },
    {
      key: 'officials',
      label: 'Officials',
      value: stateStats.civicpatch.officials,
      sub: `External: ${stateStats.external.officials}`,
      copyText: `[officials] CivicPatch: ${stateStats.civicpatch.officials} / External: ${stateStats.external.officials}`,
      description: 'Elected officials collected by CivicPatch for this state. External count comes from other datasets.',
    },
    {
      key: 'localities',
      label: 'Localities (all)',
      value: known,
      sub: `${scrapeable} scrapeable · ${stateStats.external.localities} external`,
      copyText: `[localities] ${known} total (${scrapeable} scrapeable, ${stateStats.external.localities} external)`,
      description: 'Total known jurisdictions in the state. Scrapeable = those with websites we can target. External = tracked by other datasets.',
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
      <div class="progress-bar-container" title="Total Coverage: ${actualCoverage} of ${known} known localities">
        <progress value="${actualCoverage}" max="${scrapeable}"></progress>
        <small>${percentLabel(actualCoverage, scrapeable)} covered</small>
      </div>
      <stat-cards .stats=${statsList}></stat-cards>
    </section>
  `;
}

customElements.define('summary-stats', component(SummaryStats, { useShadowDOM: false }));
export default SummaryStats;
