import { html } from 'lit-html';
import { component } from 'haunted';

function percentLabel(n, d) {
  if (!d) return '0%';
  return `${((n / d) * 100).toFixed(1)}%`;
}

const STYLES = html`
  <style>
    .states-overview {
      display: flex;
      flex-direction: column;
      gap: 1rem;
      margin-bottom: 2rem;
    }
    .states-overview__heading {
      font-size: 0.8rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--pico-muted-color);
      margin-bottom: 0.25rem;
    }
    .state-row {
      display: grid;
      grid-template-columns: 3rem 1fr 3.5rem 6rem;
      align-items: center;
      gap: 0.75rem;
      cursor: pointer;
      border-radius: var(--pico-border-radius);
      padding: 0.4rem 0.5rem;
      transition: background 0.12s ease;
    }
    .state-row:hover,
    .state-row:focus-visible {
      background: var(--pico-muted-background);
    }
    .state-row:focus-visible {
      outline: var(--pico-outline-width, 2px) solid var(--pico-primary-focus);
      outline-offset: 2px;
    }
    .state-row__code {
      font-size: 0.8rem;
      font-weight: 700;
      font-family: var(--pico-font-family-monospace);
      color: var(--pico-color);
      text-transform: uppercase;
    }
    .state-row__bar {
      width: 100%;
      height: 0.5rem;
      background: var(--pico-muted-background);
      border-radius: 999px;
      overflow: hidden;
    }
    .state-row__bar-fill {
      height: 100%;
      background: var(--pico-primary);
      border-radius: 999px;
    }
    .state-row__pct {
      font-size: 0.8rem;
      font-weight: 600;
      font-family: var(--pico-font-family-monospace);
      color: var(--pico-color);
      text-align: right;
    }
    .state-row__sub {
      font-size: 0.75rem;
      color: var(--pico-muted-color);
      font-family: var(--pico-font-family-monospace);
      white-space: nowrap;
    }
  </style>
`;

function StatesOverview({ stats }) {
  if (!stats || !stats.states) return html``;

  const states = Object.values(stats.states);

  const handleClick = (stateCode) => {
    document.dispatchEvent(
      new CustomEvent('state-select', {
        detail: { state: stateCode },
        bubbles: true,
        composed: true,
      })
    );
  };

  return html`
    ${STYLES}
    <div class="states-overview">
      <div class="states-overview__heading">Coverage by state</div>
      <div role="listbox" aria-label="Select a state">
      ${states.map((stateData) => {
        const { coverage, scrapeable } = stateData.civicpatch.localities;
        return html`
          <div
            class="state-row"
            role="option"
            aria-selected="false"
            tabindex="0"
            @click=${() => handleClick(stateData.state)}
            @keydown=${(e) => (e.key === 'Enter' || e.key === ' ') && handleClick(stateData.state)}
          >
            <span class="state-row__code">${stateData.state}</span>
            <div class="state-row__bar">
              <div class="state-row__bar-fill" style="width: ${scrapeable ? ((coverage / scrapeable) * 100).toFixed(1) : 0}%"></div>
            </div>
            <span class="state-row__pct">${percentLabel(coverage, scrapeable)}</span>
            <span class="state-row__sub">${coverage} / ${scrapeable}</span>
          </div>
        `;
      })}
      </div>
    </div>
  `;
}

customElements.define('states-overview', component(StatesOverview, { useShadowDOM: false }));
export default StatesOverview;
