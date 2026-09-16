import { html } from "lit-html";

import { comparisonPanel } from "./comparison-panel.js";
import { formatCount, scorePill, sectionLabel, shortModel } from "./format.js";

function bestScore(row) {
  const scores = row.cells.filter((cell) => cell).map((cell) => cell.mean_score);
  return scores.length < 2 ? null : Math.max(...scores);
}

function matrixCell(cell, best) {
  if (!cell) {
    return html`<td class="empty-cell">not run</td>`;
  }
  return html`
    <td>
      ${scorePill(cell.mean_score, cell.mean_score === best)}
      <span class="subtext">${formatCount(cell.run_count, "run")}</span>
    </td>
  `;
}

function matrixRow(row, isCurrentPrompt) {
  const best = bestScore(row);
  return html`
    <tr>
      <th><code>${row.prompt_sha256}</code>${isCurrentPrompt ? html`<span class="subtext">current prompt</span>` : ""}</th>
      ${row.cells.map((cell) => matrixCell(cell, best))}
    </tr>
  `;
}

function lineageHeading(lineage) {
  return html`<th>${shortModel(lineage.model)}<span class="subtext">${lineage.provider}</span></th>`;
}

function evalModels(section, choice, actions) {
  const { lineages, rows } = section.matrix;
  return html`
    ${sectionLabel(section)}
    <div class="eval-card">
      <table class="data-table model-matrix">
        <thead><tr><th>prompt</th>${lineages.map(lineageHeading)}</tr></thead>
        <tbody>${rows.map((row, index) => matrixRow(row, index === 0))}</tbody>
      </table>
      ${section.comparison ? comparisonPanel(section, choice, actions) : ""}
    </div>
  `;
}

export function modelsSection(sections, comparisonChoices, actions) {
  return html`
    <p class="note">Average case score for each prompt version (rows, newest first) on each model and
    provider (columns). The best score in a row is bold. Compare along a row: scores in different rows
    came from different prompts.</p>
    ${sections
      .filter((section) => section.matrix.rows.length)
      .map((section) => evalModels(section, comparisonChoices[section.eval_name], actions))}
  `;
}
