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

// Mirrors shared/utils/statuses.py RequestType. Only PEOPLE has a scrape behind it.
export const REQUEST_TYPE = Object.freeze({
  PEOPLE: "people",
  JURISDICTION_MANUAL_EDIT: "jurisdiction_manual_edit",
});

export interface HistoryEntry {
  request_id: string;
  created_at: string;
  request_type?: string | null;
  pull_request_url?: string | null;
  pull_request_status?: string | null;
}

export const openPullRequests = (history: HistoryEntry[]): HistoryEntry[] =>
  history.filter((entry) => entry.pull_request_status === PULL_REQUEST_STATUS.OPEN);

const isManualEdit = (entry: HistoryEntry) =>
  entry.request_type === REQUEST_TYPE.JURISDICTION_MANUAL_EDIT;

// The two kinds edit different files, so they block independently: an open scrape
// must not lock the website field, and an open website edit must not lock the
// roster. Each only blocks a second edit to the file it already has in flight.
export const peopleEditBlockers = (open: HistoryEntry[]): HistoryEntry[] =>
  open.filter((entry) => !isManualEdit(entry));

export const jurisdictionEditBlockers = (open: HistoryEntry[]): HistoryEntry[] =>
  open.filter(isManualEdit);

// GitHub numbers the PR, but history only carries its url.
const pullRequestNumber = (url?: string | null) => url?.split("/").pop() ?? "";

// Jurisdiction edits auto-merge, so one still sitting open means the merge failed.
// Editing again would branch from main — which lacks the stuck edit — and publishing
// that would silently drop it. So the block is about not losing the pending change.
export function jurisdictionEditBlockedReason(open: HistoryEntry[]): string | null {
  if (!open.length) return null;
  if (open.length > 1) {
    return `${open.length} edits did not auto-merge. Resolve or close them before editing again.`;
  }
  const number = pullRequestNumber(open[0].pull_request_url);
  const subject = number ? `Edit #${number}` : "An edit";
  return `${subject} did not auto-merge. Resolve or close it before editing again.`;
}

// Editing while a scrape PR is open would open a second PR against the same file — a
// merge conflict by construction. The list above is the way out, so the reason
// names the PR rather than just saying "disabled".
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
  const manualEdit = isManualEdit(entry);
  const number = pullRequestNumber(entry.pull_request_url);

  return html`
    <div class="pr-row">
      <div class="pr-row__main">
        <span class="pr-row__title">
          ${number ? `#${number} · ` : ""}${manualEdit ? "Website edit" : "Scrape"} of
          ${dateStringToFriendly(entry.created_at)}
        </span>
        <span class="pr-row__sub">
          ${manualEdit ? "Did not auto-merge — needs attention" : "Awaiting review"}
        </span>
      </div>
      <span class="pr-row__actions">
        ${manualEdit
          ? nothing
          : html`<a class="btn-primary" href=${pullRequestUrl(state, entry.request_id)}>
              <i class="fa-solid fa-arrow-right-to-bracket"></i> Review
            </a>`}
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

// No cap: the guards allow at most one open scrape and one stuck jurisdiction edit,
// so this list is structurally short.
export function renderOpenPullRequests(entries: HistoryEntry[], ocdid: string) {
  if (!entries.length) return nothing;

  return html`
    <section class="jurisdiction-section">
      <div class="jurisdiction-section__head">
        <h2 class="jurisdiction-section__title">Open pull requests</h2>
        <span class="jurisdiction-section__meta">${entries.length} open</span>
      </div>
      <div class="pr-list">
        ${entries.map((entry) => renderRow(entry, ocdid))}
      </div>
    </section>
  `;
}
