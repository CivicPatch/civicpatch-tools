import { html } from 'lit-html';
import { component } from 'haunted';

function renderSingleGapTable(title, list) {
  return html`
    <div>
      <strong>${title} (count: ${list.length})</strong>
      <table>
        <thead>
          <tr>
            <th>Jurisdiction OCDID</th>
          </tr>
        </thead>
        <tbody>
          ${list.map(loc => html`
            <tr>
              <td>${loc}</td>
            </tr>
          `)}
        </tbody>
      </table>
    </div>
  `;
}

function renderSideBySideTable(leftTitle, leftList, rightTitle, rightList) {
  const maxRows = Math.max(leftList.length, rightList.length);
  return html`
    <div>
      <table>
        <thead>
          <tr>
            <th>${leftTitle}</th>
            <th>${rightTitle}</th>
          </tr>
        </thead>
        <tbody>
          ${Array.from({ length: maxRows }).map((_, i) => html`
            <tr>
              <td>${leftList[i] || ''}</td>
              <td>${rightList[i] || ''}</td>
            </tr>
          `)}
        </tbody>
      </table>
    </div>
  `;
}

function LocalityGaps({ stats, state = 'TX' }) {
  if (!stats || !stats.states || !stats.states[state]) return html``;
  const gaps = stats.states[state].locality_gaps;

  return html`
    <div>
      <h3>Locality Data Gaps:</h3>
      ${renderSingleGapTable('Scrapeable but not covered', gaps.not_yet_scraped)}
      ${renderSideBySideTable(
        'In external, not in civicpatch',
        gaps.in_external_not_known,
        'In civicpatch, not in external',
        gaps.in_civicpatch_not_external
      )}
    </div>
  `;
}

customElements.define('locality-gaps', component(LocalityGaps, { useShadowDOM: false }));
export default LocalityGaps;