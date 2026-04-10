import { html } from 'lit-html';
import { useState, useEffect, component } from 'haunted';
import '../../components/progress-dashboard/summary-stats.js';
import '../../components/progress-dashboard/states-overview.js';
import { config } from '../../assets/config.js';
const API_URL = config.apiUrl;

function ProgressPage() {
  const [data, setData] = useState(null);
  const [selectedState, setSelectedState] = useState('');

  useEffect(() => {
    fetch(`${API_URL}/api/v1/data/dashboard`)
      .then(res => res.json())
      .then(data => setData(data.data));
  }, []);

  useEffect(() => {
    const handler = (e) => setSelectedState((e.detail.state || '').toLowerCase());
    document.addEventListener('state-select', handler);
    return () => document.removeEventListener('state-select', handler);
  }, []);

  if (!data) return html`<div>Loading...</div>`;

  const stateOptions = Object.keys(data.states || {});

  return html`
    <main>
      <section>
        <label for="state-select">State:</label>
        <select
          id="state-select"
          @change=${e => setSelectedState(e.target.value)}
          .value=${selectedState}
        >
          <option value="">All states</option>
          ${stateOptions.map(
            state => html`<option value=${state}>${state.toUpperCase()}</option>`
          )}
        </select>
      </section>
      <section>
        ${selectedState
          ? html`<summary-stats .stats=${data} .state=${selectedState}></summary-stats>`
          : html`<states-overview .stats=${data}></states-overview>`
        }
      </section>
    </main>
  `;
}

customElements.define('progress-page', component(ProgressPage, { useShadowDOM: false }));
export default ProgressPage;
