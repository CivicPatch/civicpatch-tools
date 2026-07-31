// Pull requests still awaiting review, listed above the roster.
//
// They are actionable — each one launches the review session for that request —
// and they are also why in-place editing is off, so they carry that explanation
// rather than leaving the disabled roster unexplained.

import { html, nothing } from "lit-html";
import { dateStringToFriendly } from "../../utils/date-utils.js";
import { jurisdictionOcdidToState } from "../../components/ocdid-utils.js";
import { pullRequestUrl } from "../review-routes.js";
import { PULL_REQUEST_STATUS } from "../../components/pull-request-card/pull-request-status.js";

export interface HistoryEntry {
  request_id: string;
  created_at: string;
  pull_request_url?: string | null;
  pull_request_status?: string | null;
}

export const openPullRequests = (history: HistoryEntry[]): HistoryEntry[] =>
  history.filter((entry) => entry.pull_request_status === PULL_REQUEST_STATUS.OPEN);

// GitHub numbers the PR, but history only carries its url.
const pullRequestNumber = (url?: string | null) => url?.split("/").pop() ?? "";

// Editing published data while a scrape PR is open would open a second PR against
// the same open-data file — a merge conflict by construction. The list above is
// the way out, so the reason names the PR rather than just saying "disabled".
export function editingBlockedReason(open: HistoryEntry[]): string | null {
  if (!open.length) return null;
  if (open.length > 1) {
    return `${open.length} pull requests are awaiting review. Publish or close them before editing directly.`;
  }
  const number = pullRequestNumber(open[0].pull_request_url);
  const subject = number ? `Pull request #${number}` : "A pull request";
  return `${subject} is awaiting review. Publish or close it before editing directly.`;
}

function renderRow(entry: HistoryEntry, ocdid: string) {
  const state = jurisdictionOcdidToState(ocdid);
  const number = pullRequestNumber(entry.pull_request_url);

  return html`
    <div class="pr-row">
      <div class="pr-row__main">
        <span class="pr-row__title">
          ${number ? `#${number} · ` : ""}Scrape of ${dateStringToFriendly(entry.created_at)}
        </span>
        <span class="pr-row__sub">Awaiting review</span>
      </div>
      <span class="pr-row__actions">
        <a class="btn-primary" href=${pullRequestUrl(state, entry.request_id)}>
          <i class="fa-solid fa-arrow-right-to-bracket"></i> Review
        </a>
        ${entry.pull_request_url
          ? html`<a
              href=${entry.pull_request_url}
              target="_blank"
              rel="noopener noreferrer"
              title="View on GitHub"
            >
              <i class="fa-brands fa-github"></i>
            </a>`
          : nothing}
      </span>
    </div>
  `;
}

export function renderOpenPullRequests(entries: HistoryEntry[], ocdid: string) {
  if (!entries.length) return nothing;

  return html`
    <section class="jurisdiction-section">
      <div class="jurisdiction-section__head">
        <h2 class="jurisdiction-section__title">Open pull requests</h2>
        <span class="jurisdiction-section__meta">
          ${entries.length} awaiting review
        </span>
      </div>
      <div class="pr-list">
        ${entries.map((entry) => renderRow(entry, ocdid))}
      </div>
    </section>
  `;
}
