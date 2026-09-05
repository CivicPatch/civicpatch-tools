// Scrapes still awaiting review, listed above the roster.
//
// They are actionable — each one launches the review session for that request —
// and they are also why in-place editing is off, so they carry that explanation
// rather than leaving the disabled roster unexplained.

import { html, nothing } from "lit-html";
import { dateStringToFriendly } from "../../utils/date-utils.js";
import { jurisdictionOcdidToState } from "../../components/ocdid-utils.js";
import { LOGIN_PATH, reviewSessionUrl } from "../review-routes.js";

// Mirrors shared/utils/statuses.py ChangesetKind — which producer made the changeset.
// Only SCRAPE has a pipeline run behind it. JURISDICTION_EDIT is here only while those edits
// still live in `changesets`; they move to their own table when the PR flow is restored.
export const CHANGESET_KIND = Object.freeze({
  SCRAPE: "scrape",
  SHEET_IMPORT: "sheet_import",
  PEOPLE_EDIT: "people_edit",
  JURISDICTION_EDIT: "jurisdiction_edit",
});

// Which table an entry came from, and so what its `id` names. Mirrors
// schemas/common.py InFlightEntryType.
export const IN_FLIGHT_ENTRY_TYPE = Object.freeze({
  PIPELINE_RUN: "pipeline_run",
  CHANGESET: "changeset",
});

// What `/jurisdictions/in-flight` returns: an attempt still running, or a proposal still
// awaiting a decision. Was `HistoryEntry`, back when the page derived all of this from the
// full history.
export interface InFlightEntry {
  // A `pipeline_runs` id until the run reaches ingest, a `changesets` id after. `entry_type`
  // is the only thing that says which — `is_running` is true in both.
  id: string;
  entry_type: string;
  created_at: string;
  kind?: string | null;
  change_url?: string | null;
  pipeline_run_status?: string | null;
  pipeline_run_progress?: number | null;
  // Derived server-side. The page used to answer this itself by testing the raw pipeline
  // status against a terminal set it kept its own copy of, so the two could drift.
  is_running?: boolean;
  // `AVAILABLE_FOR_REVIEW`, the review pool's own predicate, answered in the same query.
  awaiting_review?: boolean;
}

// `publishedAt` lived here, scanning the whole history for the newest published entry. The page
// no longer fetches the whole history — `last_published_at` comes from `/jurisdictions/in-flight`
// as `max(published_at)`, which is the same answer without the array.

/** Scrapes the review pool actually holds.
 *
 * The server answers this, because it already had to: `AVAILABLE_FOR_REVIEW` is what the queue
 * and the session both select on. Re-deriving it here from `review_status` was a second
 * definition, and it drifted — `pending` is true from the moment a request exists, so a scrape
 * still running read as awaiting review and offered a button for a roster it had not produced.
 */
export const pendingReviews = (history: InFlightEntry[]): InFlightEntry[] =>
  history.filter((entry) => entry.awaiting_review);

const isManualEdit = (entry: InFlightEntry) =>
  entry.kind === CHANGESET_KIND.JURISDICTION_EDIT;

// The two kinds edit different files, so they block independently: an open scrape
// must not lock the website field, and an open website edit must not lock the
// roster. Each only blocks a second edit to the file it already has in flight.
export const peopleEditBlockers = (open: InFlightEntry[]): InFlightEntry[] =>
  open.filter((entry) => !isManualEdit(entry));

export const jurisdictionEditBlockers = (open: InFlightEntry[]): InFlightEntry[] =>
  open.filter(isManualEdit);

// GitHub numbers the PR, but history only carries its url.
const pullRequestNumber = (url?: string | null) => url?.split("/").pop() ?? "";

// Jurisdiction edits auto-merge, so one still sitting open means the merge failed.
// Editing again would branch from main — which lacks the stuck edit — and publishing
// that would silently drop it. So the block is about not losing the pending change.
export function jurisdictionEditBlockedReason(open: InFlightEntry[]): string | null {
  if (!open.length) return null;
  if (open.length > 1) {
    return `${open.length} edits did not auto-merge. Resolve or close them before editing again.`;
  }
  const number = pullRequestNumber(open[0].change_url);
  const subject = number ? `Edit #${number}` : "An edit";
  return `${subject} did not auto-merge. Resolve or close it before editing again.`;
}

// Editing while a scrape PR is open would open a second PR against the same file — a
// merge conflict by construction. The list above is the way out, so the reason
// names the PR rather than just saying "disabled".
export function editingBlockedReason(open: InFlightEntry[]): string | null {
  if (!open.length) return null;
  if (open.length > 1) {
    return `${open.length} pull requests are awaiting review. Publish or close them before editing directly.`;
  }
  const number = pullRequestNumber(open[0].change_url);
  const subject = number ? `Pull request #${number}` : "A pull request";
  return `${subject} is awaiting review. Publish or close it before editing directly.`;
}

function renderRow(entry: InFlightEntry, ocdid: string, isSignedIn: boolean) {
  const state = jurisdictionOcdidToState(ocdid);
  const manualEdit = isManualEdit(entry);
  const number = pullRequestNumber(entry.change_url);

  return html`
    <div class="pr-row">
      <div class="pr-row__main">
        <span class="pr-row__title">
          ${number ? `#${number}: ` : ""}${manualEdit ? "Website edit" : "Scrape"} of
          ${dateStringToFriendly(entry.created_at)}
        </span>
        <span class="pr-row__sub">
          ${manualEdit ? "Did not auto-merge, needs attention" : "Awaiting review"}
        </span>
      </div>
      <span class="pr-row__actions">
        ${manualEdit
          ? nothing
          : isSignedIn
            ? html`<a class="btn-primary" href=${reviewSessionUrl(state, entry.id)}>
                <i class="fa-solid fa-arrow-right-to-bracket"></i> Review
              </a>`
            : html`<a class="btn-primary" href=${LOGIN_PATH}>
                <i class="fa-solid fa-right-to-bracket"></i> Sign in to review
              </a>`}
        ${entry.change_url
          ? html`<a
              href=${entry.change_url}
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
export function renderPendingReviews(entries: InFlightEntry[], ocdid: string, isSignedIn: boolean) {
  if (!entries.length) return nothing;

  return html`
    <section class="jurisdiction-section">
      <div class="jurisdiction-section__head">
        <h2 class="jurisdiction-section__title">Awaiting review</h2>
        <span class="jurisdiction-section__meta">${entries.length} pending</span>
      </div>
      <div class="pr-list">
        ${entries.map((entry) => renderRow(entry, ocdid, isSignedIn))}
      </div>
    </section>
  `;
}
