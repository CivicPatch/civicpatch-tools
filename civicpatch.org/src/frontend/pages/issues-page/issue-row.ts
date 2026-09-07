import { html, TemplateResult } from "lit-html";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";
import { formatDate } from "./utils.js";

export const PENDING = "pending";

export type Jurisdiction = {
  jurisdiction_ocdid: string;
  name: string;
  state: string;
};

export type Issue = {
  id: string;
  issue_type: string;
  data: { error?: string; title?: string; body?: string } | null;
  status: string;
  created_at: string | null;
  is_flagged: boolean;
  states: string[];
  jurisdictions: Jurisdiction[];
};

export type RowHandlers = {
  cells: (issue: Issue) => TemplateResult;
  isSelected: (issue: Issue) => boolean;
  onSelect: (issue: Issue) => void;
  onFlag: (issue: Issue, isFlagged: boolean) => void;
  onDetails: (issue: Issue) => void;
  onDismiss: (issue: Issue) => void;
};

// Only pending rows are selectable or dismissable — the rest are archive.
export function IssueRow(issue: Issue, handlers: RowHandlers) {
  const isPending = issue.status === PENDING;
  return html`
    <tr class=${issue.is_flagged ? "issues-page__issue-row--flagged" : ""}>
      <td class="issues-page__issue-select">
        ${isPending
          ? html`<input
              type="checkbox"
              .checked=${handlers.isSelected(issue)}
              @change=${() => handlers.onSelect(issue)}
              aria-label="Select issue"
            />`
          : null}
      </td>
      ${handlers.cells(issue)}
      <td class="issues-page__issue-jurisdictions">
        ${issue.jurisdictions?.length === 1
          ? html`
            <span class="issues-page__state-badge">${issue.jurisdictions[0].state.toUpperCase()}</span>
            <a href="/${jurisdictionOcdidToPath(issue.jurisdictions[0].jurisdiction_ocdid)}" target="_blank" rel="noopener noreferrer">${issue.jurisdictions[0].name}</a>
          `
          : (issue.states || []).map((s) => html`<span class="issues-page__state-badge">${s.toUpperCase()}</span>`)}
      </td>
      <td class="issues-page__issue-flag">
        <input
          type="checkbox"
          .checked=${!!issue.is_flagged}
          @change=${(e: Event) => handlers.onFlag(issue, (e.target as HTMLInputElement).checked)}
          title="Flagged"
        />
      </td>
      <!-- Masked in the visual suite: seeded with NOW(), so it renders the day
           the run happens on and would rot the baseline overnight. -->
      <td class="issues-page__issue-date" data-visual-volatile>${formatDate(issue.created_at)}</td>
      <td>
        <div class="issues-page__issue-actions">
          <button class="civ-action-btn" @click=${() => handlers.onDetails(issue)}>Details</button>
          ${isPending
            ? html`<button class="civ-action-btn civ-action-btn--danger" @click=${() => handlers.onDismiss(issue)}>Dismiss</button>`
            : null}
        </div>
      </td>
    </tr>
  `;
}
