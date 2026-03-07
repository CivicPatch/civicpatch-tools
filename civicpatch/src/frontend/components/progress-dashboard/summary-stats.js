import { html } from 'lit-html';
import { component } from 'haunted';

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

  const progress = percent(actualCoverage, scrapeable);

  return html`
    <style>
      .progress-bar-container {
        width: 100%;
        max-width: 900px;
        margin: 0 auto 2rem auto;
        /* Remove custom background and border-radius for Pico default */
        height: 2.5rem;
        display: flex;
        align-items: center;
        position: relative;
        box-shadow: 0 1px 4px rgba(0,0,0,0.03);
        background: none;
        border-radius: 0;
      }
      .progress-bar-fill {
        /* Remove custom background and border-radius for Pico default */
        height: 100%;
        transition: width 0.5s cubic-bezier(.4,2,.6,1);
        display: flex;
        align-items: center;
        justify-content: flex-end;
        color: #fff;
        font-size: 1.5rem;
        font-weight: 700;
        padding-right: 2rem;
        box-sizing: border-box;
        min-width: 3.5rem;
        background: none;
        border-radius: 0;
      }
      .progress-bar-label {
        position: absolute;
        left: 50%;
        top: 50%;
        transform: translate(-50%, -50%);
        font-size: 1.3rem;
        font-weight: 600;
        color: var(--pico-primary-inverse, #fff);
        letter-spacing: 0.03em;
        pointer-events: none;
        text-shadow: 0 1px 2px rgba(0,0,0,0.10);
      }
      .summary-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        gap: 2rem;
        max-width: 900px;
        margin: 0 auto;
      }
      .stat-card {
        background: var(--pico-muted-background, #f8fafc);
        border-radius: 1rem;
        padding: 1.5rem 1.2rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.03);
        display: flex;
        flex-direction: column;
        align-items: flex-start;
      }
      .stat-label {
        font-size: 1rem;
        color: var(--pico-muted-color, #666);
        margin-bottom: 0.2em;
      }
      .stat-main {
        font-size: 2.2rem;
        font-weight: 700;
        color: var(--pico-primary, #2563eb);
        line-height: 1.1;
      }
      .stat-sub {
        font-size: 0.98rem;
        color: var(--pico-muted-color, #888);
        margin-top: 0.2em;
      }
    </style>
    <section>
      <div class="progress-bar-container" title="Total Coverage: ${actualCoverage} of ${known} known localities">
        <progress value="${actualCoverage}" max="${scrapeable}" style="width:100%;height:2.5rem;"></progress>
        <span class="progress-bar-label">${percentLabel(actualCoverage, scrapeable)} covered</span>
      </div>
      <div class="summary-grid">
        <div class="stat-card">
          <div class="stat-label">Scrapeable Coverage</div>
          <div class="stat-main">${percentLabel(actualCoverage, scrapeable)}</div>
          <div class="stat-sub" title="${actualCoverage} of ${scrapeable} scrapeable">
            ${actualCoverage} of ${scrapeable} scrapeable
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Total Coverage</div>
          <div class="stat-main">${percentLabel(actualCoverage, known)}</div>
          <div class="stat-sub" title="${actualCoverage} of ${known} known">
            ${actualCoverage} of ${known} known
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Officials</div>
          <div class="stat-main">${stateStats.civicpatch.officials}</div>
          <div class="stat-sub">
            CivicPatch<br>
            <span style="font-size:0.95em;">External: ${stateStats.external.officials}</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Localities (all)</div>
          <div class="stat-main">${known}</div>
          <div class="stat-sub">
            ${scrapeable} scrapeable<br>
            ${stateStats.external.localities} external
          </div>
        </div>
      </div>
    </section>
  `;
}

customElements.define('summary-stats', component(SummaryStats, { useShadowDOM: false }));
export default SummaryStats;