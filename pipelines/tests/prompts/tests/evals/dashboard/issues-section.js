import { html } from "lit-html";

import { caseLink, joinTemplates } from "./format.js";

const ISSUE_KIND = {
  CASES_FAILED: "cases_failed",
  GATE_FAILED: "gate_failed",
  MANY_MISSING: "many_missing",
  WIDE_SWING: "wide_swing",
};
const SEVERITY_CLASS = ["issue--blocking", "issue--gap", "issue--noise"];

function issueText(issue, section) {
  const provider = html`<b>${issue.provider}</b>`;
  const metric = html`<code>${issue.metric}</code>`;
  switch (issue.kind) {
    case ISSUE_KIND.CASES_FAILED: {
      const cases = joinTemplates(issue.failed_case_ids.map((caseId) => caseLink(section, caseId)));
      return html`${provider} fails ${issue.failed_case_ids.length} case(s) in <code>${issue.eval_name}</code>: ${cases}.`;
    }
    case ISSUE_KIND.GATE_FAILED:
      return html`${provider} fails the ${metric} gate. Scored <b>${issue.score.toFixed(3)}</b>, floor is ${issue.gate_floor.toFixed(2)}.`;
    case ISSUE_KIND.MANY_MISSING:
      return html`${provider} missed <b>${issue.missing_count} of ${issue.expected_count}</b> ${metric} values.`;
    case ISSUE_KIND.WIDE_SWING:
      return html`${provider}&rsquo;s ${metric} swung <b>&plusmn;${issue.swing.toFixed(2)}</b> between identical runs, so it is not a quality signal.`;
    default:
      return html`${provider}: ${issue.kind}`;
  }
}

export function issuesSection(issues, sections) {
  if (!issues.length) {
    return html`<div class="eval-card"><p class="note">Nothing to fix: no gate failures, no large gaps.</p></div>`;
  }
  const sectionFor = (issue) => sections.find((section) => section.eval_name === issue.eval_name);
  return html`
    <div class="eval-card">
      <ul class="issue-list">
        ${issues.map((issue) => html`
          <li class="issue ${SEVERITY_CLASS[issue.severity]}">${issueText(issue, sectionFor(issue))}</li>
        `)}
      </ul>
    </div>
  `;
}
