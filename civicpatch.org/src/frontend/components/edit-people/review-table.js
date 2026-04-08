import { html, component, useState, useEffect } from 'haunted';

const ORIGIN_SOURCE_LABELS = {
  google_gemini: "Google Gemini",
  existing: "Existing",
};

function ReviewTable({ jurisdiction_ocdid, branch_name, reviewData, currentPeople }) {
  const researchLabel = ORIGIN_SOURCE_LABELS[reviewData?.origin_source] ?? "Research";

  function renderCheckmark(value) {
    return value
      ? html`<i class="fa-solid fa-check" style="color: var(--pico-ins-color, #4caf50);"></i>`
      : html`<i class="fa-solid fa-xmark" style="color: var(--pico-del-color, #e53935);"></i>`;
  }

  function renderIssues() {
    if (!reviewData?.issues?.length) return '';
    return html`
      <div class="review-issues">
        <h4 class="review-issues__heading">Issues</h4>
        <ul class="review-issues__list">
          ${reviewData.issues.map(issue => html`
            <li class="review-issues__item">
              <i class="fa-solid fa-triangle-exclamation review-issues__icon"></i>
              ${issue}
            </li>
          `)}
        </ul>
      </div>
    `;
  }

  function renderTable() {
    if (!reviewData?.people_by_source?.length) {
      return html`<p>No data to display.</p>`;
    }

    return html`
      <table role="grid">
        <thead>
          <tr>
            <th>Name</th>
            <th style="text-align: center;">${researchLabel}</th>
            <th style="text-align: center;">Data</th>
          </tr>
        </thead>
        <tbody>
          ${reviewData.people_by_source.map(row => html`
            <tr class=${getRowClass(row)}>
              <td>${row.name}</td>
              <td style="text-align: center;">${renderCheckmark(row.in_research)}</td>
              <td style="text-align: center;">${renderCheckmark(row.in_data)}</td>
            </tr>
          `)}
        </tbody>
      </table>
    `;
  }

  function getRowClass(row) {
    if (!row.in_research && row.in_data) return 'row-extra';
    if (row.in_research && !row.in_data) return 'row-missing';
    return '';
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
  component(ReviewTable, {
    useShadowDOM: false,
    observedAttributes: ['jurisdiction_ocdid', 'branch_name']
  })
);