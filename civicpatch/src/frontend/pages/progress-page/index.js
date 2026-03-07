import { html } from 'lit-html';
import { useState, useEffect, component } from 'haunted';
import '../../components/progress-dashboard/summary-stats.js';
import '../../components/progress-dashboard/locality-gaps.js';
const API_URL = __API_URL__;

function ProgressPage() {
  const [data, setData] = useState(null);
  const [selectedState, setSelectedState] = useState('TX');

  useEffect(() => {
    fetch(`${API_URL}/api/v1/data/dashboard`)
      .then(res => res.json())
      .then(data => setData(data.data));
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
          ${stateOptions.map(
            state => html`<option value=${state}>${state}</option>`
          )}
        </select>
      </section>
      <section>
        <summary-stats .stats=${data} .state=${selectedState}></summary-stats>
        <locality-gaps .stats=${data} .state=${selectedState}></locality-gaps>
      </section>
    </main>
  `;
}

customElements.define('progress-page', component(ProgressPage, { useShadowDOM: false }));
export default ProgressPage;