import { html } from "lit-html";

import { caseLink, formatCount, formatValue, lineageLabel } from "./format.js";

function lineagePicker(label, lineages, selectedIndex, onPick) {
  return html`
    <label>
      ${label}
      <select @change=${(e) => onPick(Number(e.target.value))}>
        ${lineages.map((lineage, index) => html`
          <option value=${index} ?selected=${index === selectedIndex}>${lineageLabel(lineage)}</option>
        `)}
      </select>
    </label>
  `;
}

function scoreDelta(pair) {
  const delta = pair.candidate.mean_score - pair.baseline.mean_score;
  const direction = delta < 0 ? "worse" : "better";
  const sign = delta < 0 ? "−" : "+";
  return html`<span class="delta delta--${direction}">${sign}${Math.abs(delta).toFixed(2)}</span>`;
}

function runsAndCost(cell) {
  const cost = cell.mean_cost_usd == null ? "" : `, $${cell.mean_cost_usd.toFixed(4)} per run`;
  return `${formatCount(cell.run_count, "run")}${cost}`;
}

function summary(pair, baseline, candidate) {
  if (!pair.prompt_sha256) {
    return html`<p class="comparison__summary">These two never ran the same prompt, so there is no fair
    comparison. Run both on the current prompt.</p>`;
  }
  return html`
    <p class="comparison__summary">
      On prompt <code>${pair.prompt_sha256}</code>, ${lineageLabel(baseline)} averages
      <b>${pair.baseline.mean_score.toFixed(2)}</b> (${runsAndCost(pair.baseline)}) and
      ${lineageLabel(candidate)} averages <b>${pair.candidate.mean_score.toFixed(2)}</b>
      (${runsAndCost(pair.candidate)}): ${scoreDelta(pair)}.
    </p>
  `;
}

function caseChangeTable(section, title, changes) {
  if (!changes.length) {
    return "";
  }
  return html`
    <details open>
      <summary>${title} (${changes.length})</summary>
      <table class="data-table">
        <thead><tr><th>case</th><th>current</th><th>compared</th></tr></thead>
        <tbody>
          ${changes.map((change) => html`
            <tr>
              <th>${caseLink(section, change.case_id)}</th>
              <td>${change.baseline_score.toFixed(2)}</td>
              <td>${change.candidate_score.toFixed(2)}</td>
            </tr>
          `)}
        </tbody>
      </table>
    </details>
  `;
}

function valueChangeTable(section, title, wrongHeading, changes) {
  if (!changes.length) {
    return "";
  }
  return html`
    <details>
      <summary>${title} (${changes.length})</summary>
      <table class="data-table mismatch-table">
        <thead><tr><th>case</th><th>person</th><th>field</th><th>expected</th><th>${wrongHeading}</th></tr></thead>
        <tbody>
          ${changes.map((change) => html`
            <tr>
              <th>${caseLink(section, change.case_id)}</th>
              <td>${change.person}</td>
              <td class="mismatch-table__field">${change.field}</td>
              <td class="mismatch-table__expected">${formatValue(change.expected)}</td>
              <td class="mismatch-table__actual">${formatValue(change.actual)}</td>
            </tr>
          `)}
        </tbody>
      </table>
    </details>
  `;
}

function valueDetail(section, pair) {
  if (!pair.has_value_detail) {
    return html`<p class="note">No value-level detail: it needs archived wrong values for both runs, and
    only the officials eval records them.</p>`;
  }
  return html`
    <p class="note">Values compare each side&rsquo;s latest run; the case scores above average all of them.</p>
    ${valueChangeTable(section, "Values the compared model gets wrong", "compared got", pair.newly_wrong)}
    ${valueChangeTable(section, "Values the compared model fixes", "current got", pair.fixed)}
  `;
}

function pairDetail(section, pair) {
  if (!pair.prompt_sha256) {
    return "";
  }
  return html`
    ${caseChangeTable(section, "Cases that got worse", pair.regressed)}
    ${caseChangeTable(section, "Cases that got better", pair.improved)}
    <p class="note">${formatCount(pair.unchanged_count, "case")} scored the same.</p>
    ${valueDetail(section, pair)}
  `;
}

export function comparisonPanel(section, choice, actions) {
  const { comparison, matrix } = section;
  const baselineIndex = choice ? choice.baseline_index : comparison.default_baseline_index;
  const candidateIndex = choice ? choice.candidate_index : comparison.default_candidate_index;
  const pick = (patch) => actions.chooseComparison(section.eval_name, {
    baseline_index: baselineIndex, candidate_index: candidateIndex, ...patch,
  });
  const pair = comparison.pairs.find(
    (p) => p.baseline_index === baselineIndex && p.candidate_index === candidateIndex,
  );
  return html`
    <div class="comparison">
      <div class="comparison__pickers">
        ${lineagePicker("Compare current", matrix.lineages, baselineIndex, (index) => pick({ baseline_index: index }))}
        ${lineagePicker("with", matrix.lineages, candidateIndex, (index) => pick({ candidate_index: index }))}
      </div>
      ${pair
        ? html`${summary(pair, matrix.lineages[baselineIndex], matrix.lineages[candidateIndex])}${pairDetail(section, pair)}`
        : html`<p class="comparison__summary">Pick two different models to compare.</p>`}
    </div>
  `;
}
