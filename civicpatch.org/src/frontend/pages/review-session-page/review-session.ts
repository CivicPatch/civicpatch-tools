import { html } from "lit-html";
import { component, useState } from "haunted";
import "../../components/review-checklist/review-checklist.js";
import "../../components/people-diff/people-diff.js";
import "../../components/source-content/source-content-debug-modal.js";
import { type Progress } from "./review-session-controls.js";
import "./review-session-controls.js";
import "./report-issue-button.js";
import { useReviewPeople } from "./use-review-people.js";
import { ReviewMode, type ReviewModeValue } from "./review-state.js";

type CurrentEntry = {
  request_id: string;
  jurisdiction: { ocdid: string | null; name: string | null; path?: string | null; website_url?: string | null };
  pr: { url: string | null; status: string | null; reviewState: string | null; number?: number | null };
  mode: ReviewModeValue;
  pr_people: { existing: any[]; proposed: any[] };
  review_data: any;
  source_content_urls: any[];
  is_read_only: boolean;
  has_next: boolean;
};

// One entry under review: what it is, and the reviewer's working copy of its
// people. The card owns those edits, so it also owns the actions that commit
// them — publishing and saving carry the patch out in the event, and the page
// decides what that means for the session.
const MERGE_EVENT = "merge";
const SAVE_EVENT = "save";
const CLOSE_PR_EVENT = "close-pr";
const END_SESSION_EVENT = "end-session";

// Everything else the card needs is derived from `currentEntry`; these are the
// things only the page can know.
type ReviewSessionHost = HTMLElement & {
  progress: Progress;
  hasSession: boolean;
  currentEntry: CurrentEntry | null;
  error: string | null;
  canClosePr: boolean;
  isClosingPr: boolean;
};

function ReviewSession(host: ReviewSessionHost) {
  const { progress, hasSession, currentEntry, error, canClosePr, isClosingPr } = host;
  const { jurisdiction, pr, mode, pr_people, review_data, source_content_urls, is_read_only, has_next } = currentEntry ?? {} as Partial<CurrentEntry>;
  const { ocdid: jurisdictionOcdid, name: jurisdictionName, website_url: jurisdictionWebsiteUrl } = jurisdiction ?? {};
  const { url: pullRequestUrl, status: pullRequestStatus = null } = pr ?? {};
  const isBaseline = mode === ReviewMode.BASELINE;

  const {
    currentPeople,
    dirty,
    peoplePatch,
    handleAdd,
    handleReset,
    updatePerson,
  } = useReviewPeople(currentEntry);

  const [debugOpen, setDebugOpen] = useState(false);
  const hasSourceContent = Boolean(source_content_urls && source_content_urls.length > 0);

  const requestId = currentEntry?.request_id ?? null;

  // A clean card publishes what the server already has; only send a patch when
  // the reviewer actually changed something.
  const handleMerge = () =>
    host.dispatchEvent(
      new CustomEvent(MERGE_EVENT, { detail: { people: dirty ? peoplePatch : null }, bubbles: true, composed: true }),
    );

  const handleSave = () =>
    host.dispatchEvent(
      new CustomEvent(SAVE_EVENT, { detail: { people: peoplePatch }, bubbles: true, composed: true }),
    );

  const handleClosePr = () =>
    host.dispatchEvent(new CustomEvent(CLOSE_PR_EVENT, { bubbles: true, composed: true }));

  const handleEndSession = () =>
    host.dispatchEvent(new CustomEvent(END_SESSION_EVENT, { bubbles: true, composed: true }));

  const handlePersonSave = (id: string, updates: Record<string, unknown>) => updatePerson(id, updates);
  const handleResetPerson = (id: string) => handleReset(id);

  return html`
    <main class="review-page">
      <div class="review-page__header">
        <review-session-controls
          .progress=${progress}
          .hasSession=${hasSession}
          .hasNext=${has_next}
        ></review-session-controls>
        <div class="review-page__actions">
          ${is_read_only ? "" : html`
          ${dirty ? html`
          <button class="btn-sm review-page__save-btn" @click=${handleSave}>Save for later</button>
          ` : ""}
          <button class="btn-sm review-page__merge-btn btn-gradient" @click=${handleMerge}>
            ${dirty ? "Save and Publish" : "Publish"}
          </button>
          ${canClosePr ? html`
          <button class="btn-sm destructive" @click=${handleClosePr} ?disabled=${isClosingPr}>
            ${isClosingPr ? "Closing..." : "Close PR"}
          </button>
          ` : ""}
          `}
          <button class="btn-sm review-page__end-btn" @click=${handleEndSession}>${hasSession ? "End session" : "Exit"}</button>
        </div>
      </div>
      ${error ? html`<p class="review-page__error">${error}</p>` : ""}
      <div class="review-page__info-row">
        <div class="review-page__pr-meta">
          ${jurisdictionName
            ? html`<a class="review-page__jurisdiction" href="/${jurisdiction?.path}" target="_blank" rel="noopener">
                ${jurisdictionName} <i class="fa-solid fa-arrow-up-right-from-square"></i>
              </a>`
            : ""}
          ${jurisdictionWebsiteUrl
            ? html`<a class="review-page__jurisdiction-website" href=${jurisdictionWebsiteUrl} target="_blank" rel="noopener">
                ${jurisdictionWebsiteUrl} <i class="fa-solid fa-arrow-up-right-from-square"></i>
              </a>`
            : ""}
          ${pullRequestUrl ? html`<a class="btn btn-sm" href=${pullRequestUrl} target="_blank" rel="noopener">View PR <i class="fa-solid fa-arrow-up-right-from-square"></i></a>` : ""}
          ${hasSourceContent ? html`<button class="btn btn-sm secondary" @click=${() => setDebugOpen(true)}>Debug</button>` : ""}
          <report-issue-button .requestId=${requestId}></report-issue-button>
        </div>
        <civ-review-checklist .reviewData=${review_data}></civ-review-checklist>
      </div>
      ${is_read_only ? html`<div class="review-page__status-banner review-page__status-banner--${pullRequestStatus}">${pullRequestStatus}</div>` : ""}
      ${isBaseline
        ? html`<div class="review-page__baseline-banner">First capture for ${jurisdictionName ?? "this jurisdiction"} — nothing to compare against yet. Publishing creates these records for the first time.</div>`
        : ""}
      <people-diff
        .existing=${pr_people?.existing ?? []}
        .currentPeople=${currentPeople ?? []}
        .issues=${review_data?.issues ?? []}
        .onPersonSave=${handlePersonSave}
        .onAdd=${handleAdd}
        .onResetPerson=${handleResetPerson}
        .jurisdictionOcdid=${jurisdictionOcdid}
        .isReadOnly=${is_read_only}
      ></people-diff>
      ${debugOpen
        ? html`
            <source-content-debug-modal
              .sourceContentUrls=${source_content_urls}
              @modal-close=${() => setDebugOpen(false)}
            ></source-content-debug-modal>
          `
        : null}
    </main>
  `;
}

customElements.define(
  "review-session",
  component(ReviewSession as unknown as () => unknown, { useShadowDOM: false }),
);
