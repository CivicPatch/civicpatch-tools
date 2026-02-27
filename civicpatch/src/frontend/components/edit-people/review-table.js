import { html, component, useState, useEffect } from 'haunted';

const API_URL = __API_URL__;

function ReviewTable({ jurisdiction_ocdid, branch_name, reviewData, currentPeople }) {
  function renderCheckmark(value) {
    return value ? '✅' : '❌';
  }

  function renderIssues() {
    if (!reviewData?.issues?.length) return '';

    return html`
      <div class="review-issues" style="margin-bottom: 1rem;">
        <h4 style="color: var(--pico-del-color, #c00);">Issues</h4>
        <ul>
          ${reviewData.issues.map(issue => html`<li>${issue}</li>`)}
        </ul>
      </div>
    `;
  }

  function renderTable() {
    if (!reviewData?.people_by_source?.length) {
      return html`<p>No data to display.</p>`;
    }

    const llmNames = reviewData.llm_names || [];

    return html`
      <table role="grid">
        <thead>
          <tr>
            <th>Name</th>
            <th style="text-align: center;">Research</th>
            ${llmNames.map(llm => html`<th style="text-align: center;">${formatLlmName(llm)}</th>`)}
            <th style="text-align: center;">Final</th>
          </tr>
        </thead>
        <tbody>
          ${reviewData.people_by_source.map(row => html`
            <tr class=${getRowClass(row)}>
              <td>${row.name}</td>
              <td style="text-align: center;">${renderCheckmark(row.in_research)}</td>
              ${llmNames.map(llm => html`<td style="text-align: center;">${renderCheckmark(row[llm])}</td>`)}
              <td style="text-align: center;">${renderCheckmark(row.in_final)}</td>
            </tr>
          `)}
        </tbody>
      </table>
    `;
  }

  function getRowClass(row) {
    if (!row.in_research && row.in_final) return 'row-extra';
    if (row.in_research && !row.in_final) return 'row-missing';
    return '';
  }

  function formatLlmName(name) {
    const map = {
      'google_gemini': 'Gemini',
      'openai': 'OpenAI',
      'anthropic': 'Claude',
    };
    return map[name] || name;
  }

  if (!reviewData) {
    return html`<p>No review data available.</p>`;
  }

  return html`
    <style>
      .row-extra {
        background-color: var(--pico-ins-color, #d4edda);
      }
      .row-missing {
        background-color: var(--pico-del-color, #f8d7da);
      }
    </style>
    <div class="review-table-container">
      <h3>Identity Comparison</h3>
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