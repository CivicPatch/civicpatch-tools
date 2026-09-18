import { html, nothing } from "lit-html";

import { formatAgo, formatFriendly, joinTemplates, sectionLabel } from "./format.js";

function verdictSummary(verdict) {
  if (verdict.cases_total) {
    return `${verdict.cases_passed} of ${verdict.cases_total} cases pass`;
  }
  return joinTemplates(
    Object.entries(verdict.priority_scores).map(([metric, score]) => html`${metric} <b>${score.toFixed(2)}</b>`),
  );
}

function promptOfLatestRun(section, verdict) {
  const version = section.prompt_versions.find((v) =>
    v.runs.some((run) => run.provider === verdict.provider && run.timestamp === verdict.ran_at));
  return version && version.prompt_sha256;
}

function caseButton(section, verdict, caseId, metric, actions) {
  const open = () => actions.openBrowser({
    eval_name: section.eval_name,
    prompt_sha256: promptOfLatestRun(section, verdict),
    timestamp: verdict.ran_at,
    provider: verdict.provider,
    metric,
    focused_case_id: caseId,
  });
  return html`<button type="button" class="case-link" @click=${open}><code>${caseId}</code></button>`;
}

function gateFailureCase(section, verdict, failure, caseCount, actions) {
  return html`${caseCount.count} in ${caseButton(section, verdict, caseCount.case_id, failure.metric, actions)}`;
}

function gateFailure(section, verdict, failure, actions) {
  if (!failure.cases.length) {
    return html`<code>${failure.metric}</code>`;
  }
  const cases = joinTemplates(failure.cases.map((caseCount) => gateFailureCase(section, verdict, failure, caseCount, actions)));
  return html`<code>${failure.metric}</code>: ${cases}`;
}

function verdictFailures(section, verdict, actions) {
  if (!verdict.blocked) {
    return nothing;
  }
  const detail = verdict.gate_failures.length
    ? joinTemplates(verdict.gate_failures.map((failure) => gateFailure(section, verdict, failure, actions)), "; ")
    : joinTemplates(verdict.failed_case_ids.map((caseId) => caseButton(section, verdict, caseId, null, actions)));
  return html`<span class="verdict__failures">fails ${detail}</span>`;
}

function verdictRow(section, verdict, actions) {
  return html`
    <div class="verdict ${verdict.blocked ? "verdict--blocked" : "verdict--ready"}">
      <span class="verdict__provider">${verdict.provider}</span>
      <span class="verdict__badge">${verdict.blocked ? "BLOCKED" : "READY"}</span>
      <span class="verdict__summary">${verdictSummary(verdict)}</span>
      <span class="verdict__cost">${verdict.cost_usd == null ? "" : `$${verdict.cost_usd.toFixed(4)}`}</span>
      ${verdict.ran_at
        ? html`<span class="verdict__ran-at" title=${formatFriendly(verdict.ran_at)}>${formatAgo(verdict.ran_at)}</span>`
        : nothing}
      ${verdictFailures(section, verdict, actions)}
    </div>
  `;
}

export function verdictSection(sections, actions) {
  return sections
    .filter((section) => section.verdicts.length)
    .map((section) => html`
      ${sectionLabel(section)}
      <div class="eval-card">${section.verdicts.map((verdict) => verdictRow(section, verdict, actions))}</div>
    `);
}
