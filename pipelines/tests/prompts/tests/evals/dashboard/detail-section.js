import { html } from "lit-html";

import { caseLink, EMPTY_VALUE, scorePill } from "./format.js";

const LOW_SCORE = 0.75;
const STABILITY_LABEL = { steady: "steady", moves: "moves" };

function scoreBar(score) {
  if (score == null) {
    return html`<span class="score-bar"><span class="score-bar__rail"></span><span class="score-bar__value">${EMPTY_VALUE}</span></span>`;
  }
  // A true zero draws a tick, not nothing: an empty bar reads as "no data".
  const fill = score === 0
    ? html`<span class="score-bar__zero"></span>`
    : html`<span class="score-bar__fill${score < LOW_SCORE ? " score-bar__fill--low" : ""}" style="width:${(score * 100).toFixed(1)}%"></span>`;
  return html`<span class="score-bar"><span class="score-bar__rail">${fill}</span><span class="score-bar__value">${score.toFixed(3)}</span></span>`;
}

function metricCell(cell) {
  if (!cell) {
    return html`<td class="empty-cell">${EMPTY_VALUE}</td>`;
  }
  return html`
    <td>
      ${scoreBar(cell.score)}
      ${cell.swing_is_wide ? html`<span class="swing-warning">±${cell.half_swing.toFixed(2)}</span>` : ""}
      ${cell.missing_count ? html`<span class="subtext">${cell.missing_count} missing</span>` : ""}
    </td>
  `;
}

function metricsTable(section) {
  const { detail } = section;
  return html`
    <details>
      <summary>${section.eval_name}, all metrics</summary>
      <table class="data-table">
        <thead><tr><th></th>${detail.providers.map((provider) => html`<th>${provider}</th>`)}</tr></thead>
        <tbody>
          ${detail.metric_rows.map((row) => html`<tr><th>${row.metric}</th>${row.cells.map(metricCell)}</tr>`)}
        </tbody>
      </table>
    </details>
  `;
}

function stabilityLabel(stability) {
  const label = STABILITY_LABEL[stability];
  return label ? html`<span class="stability--${stability}">${label}</span>` : "";
}

function movement(item) {
  const nothingMoved = !item.regressed.length && !item.improved.length;
  return html`
    <p class="note"><b>${item.provider}</b></p>
    ${nothingMoved ? html`<p class="note">no case changed between the last two runs</p>` : ""}
    ${item.regressed.length ? html`<p class="note"><span class="stability--moves">regressed</span> ${item.regressed.join(", ")}</p>` : ""}
    ${item.improved.length ? html`<p class="note"><span class="stability--steady">improved</span> ${item.improved.join(", ")}</p>` : ""}
  `;
}

function caseScore(score) {
  return score == null ? html`<td class="empty-cell">${EMPTY_VALUE}</td>` : html`<td>${scorePill(score)}</td>`;
}

function casesTable(section) {
  const { detail } = section;
  if (!detail.case_rows.length) {
    return "";
  }
  return html`
    <details>
      <summary>${section.eval_name}, per case, worst first</summary>
      ${detail.movements.map(movement)}
      <p class="note"><span class="stability--steady">steady</span> never moved across runs, so a change there
      is real. <span class="stability--moves">moves</span> varies on an unchanged prompt.</p>
      <table class="data-table">
        <thead><tr><th></th>${detail.case_providers.map((provider) => html`<th>${provider}</th>`)}<th></th></tr></thead>
        <tbody>
          ${detail.case_rows.map((row) => html`
            <tr>
              <th>${caseLink(section, row.case_id)}</th>
              ${row.scores.map(caseScore)}
              <td>${stabilityLabel(row.stability)}</td>
            </tr>
          `)}
        </tbody>
      </table>
    </details>
  `;
}

export function detailSection(sections) {
  return html`
    <div class="eval-card">
      ${sections.filter((section) => section.detail).map((section) => html`${metricsTable(section)}${casesTable(section)}`)}
    </div>
  `;
}
