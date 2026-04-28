import { html } from "lit-html";
import { getIssueTypeConfig, formatIssueType, formatDate, getIssueDetail } from "./utils.js";

export function IssueRow(issue, { onDetails, onDismiss, onConfig, onFlag }) {
  const config = getIssueTypeConfig(issue.issue_type);
  const categoryClass = config?.category ? ` issues-page__issue-type-chip--${config.category}` : "";

  return html`
    <tr class=${issue.is_flagged ? "issues-page__issue-row--flagged" : ""}>
      <td>
        <span class="issues-page__issue-type-chip issues-page__issue-type-chip--${issue.issue_type.replace(/_/g, "-")}${categoryClass}">
          ${formatIssueType(issue.issue_type)}
        </span>
      </td>
      <td class="issues-page__issue-detail">${getIssueDetail(issue.issue_type, issue.issue_key, issue.data)}</td>
      <td class="issues-page__issue-jurisdictions">
        ${issue.jurisdictions && issue.jurisdictions.length === 1
          ? html`
            <span class="issues-page__state-badge">${issue.jurisdictions[0].state.toUpperCase()}</span>
            <a href="/${issue.jurisdictions[0].path}" target="_blank" rel="noopener noreferrer">${issue.jurisdictions[0].name}</a>
          `
          : (issue.states || []).map((s) => html`<span class="issues-page__state-badge">${s.toUpperCase()}</span>`)
        }
      </td>
      <td class="issues-page__issue-status">
        ${issue.status === "pr_opened"
          ? html`<a class="issues-page__issue-status-link" href=${issue.pull_request_url} target="_blank" rel="noopener noreferrer">PR opened →</a>`
          : html`<span class="issues-page__issue-status-badge">Pending</span>`}
      </td>
      <td class="issues-page__issue-flag">
        <input type="checkbox" .checked=${!!issue.is_flagged} @change=${(e) => onFlag(issue, e.target.checked)} title="Flagged" />
      </td>
      <td class="issues-page__issue-date">${formatDate(issue.created_at)}</td>
      <td>
        <div class="issues-page__issue-actions">
          <button class="btn btn-sm secondary" @click=${() => onDetails(issue)}>Details</button>
          ${issue.issue_type === "unrecognized_role" && issue.jurisdictions?.length
            ? html`<button class="btn btn-sm" @click=${() => onConfig(issue.jurisdictions)}>Resolve</button>`
            : ""}
          ${issue.status === "pending"
            ? html`<button class="btn btn-sm destructive" @click=${() => onDismiss(issue)}>Dismiss</button>`
            : ""}
        </div>
      </td>
    </tr>
  `;
}
