import { html, component } from 'haunted';
// The same comparison the review drawer draws. Shared so the two cannot disagree
// about which direction is a gain — they did, once.
import '../people-by-source/people-by-source.ts';

function ReviewTable({ reviewData }) {
  function renderIssues() {
    if (!reviewData?.issues?.length) return '';
    return html`
      <div class="review-issues">
        <h4 class="review-issues__heading">Issues</h4>
        <ul class="review-issues__list">
          ${reviewData.issues.map(issue => html`
            <li class="review-issues__item">
              <i class="fa-solid fa-triangle-exclamation review-issues__icon"></i>
              ${issue.message}
            </li>
          `)}
        </ul>
      </div>
    `;
  }

  function renderTable() {
    return html`<civ-people-by-source
      .rows=${reviewData?.people_by_source ?? []}
      .originSource=${reviewData?.origin_source ?? null}
    ></civ-people-by-source>`;
  }

  if (!reviewData) {
    return html`<p>No review data available.</p>`;
  }

  return html`
    <div class="review-table-container">
      <h3>Results</h3>
      ${renderIssues()}
      ${renderTable()}
    </div>
  `;
}

customElements.define(
  'civ-review-table',
  component(ReviewTable, { useShadowDOM: false })
);