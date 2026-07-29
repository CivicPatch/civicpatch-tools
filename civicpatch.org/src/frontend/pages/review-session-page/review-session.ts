import { html } from "lit-html";
import { component, useState } from "haunted";
import "../../components/review-checklist/review-checklist.js";
import "../../components/review-rail/review-rail-list.js";
import "../../components/review-overview/review-overview.js";
import "../../components/review/review-modal.js";
import "../../components/source-content/source-content-debug-modal.js";
import { type Progress } from "./review-session-controls.js";
import "./review-session-controls.js";
import "./report-issue-button.js";
import { useReviewPeople } from "./use-review-people.js";
import { updateParams } from "./use-review-session.js";
import { useFrozenFields } from "./use-frozen-fields.js";
import { ReviewMode, type ReviewModeValue } from "./review-state.js";
import { buildReviewCards, cardFields, groupCards, needsReview } from "../../components/review/review-cards.js";
import { linkCandidatesFrom, railPropsFor } from "../../components/review-rail/rail-props.js";
import { parseReviewView, ReviewView, VIEW_PARAM, type ReviewViewKey } from "../review-routes.js";

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
    dirtyIds,
    deletedIds,
    restoredIds,
    dirty,
    peoplePatch,
    handleAdd,
    handleReset,
    handleDelete,
    handleUndelete,
    handleRestore,
    handleUndoRestore,
    updatePerson,
  } = useReviewPeople(currentEntry);

  const [debugOpen, setDebugOpen] = useState(false);
  const hasSourceContent = Boolean(source_content_urls && source_content_urls.length > 0);

  const requestId = currentEntry?.request_id ?? null;

  // Which view is open. Held as state, not read from the URL each render: replaceState does not
  // re-render, and the tab bar (§17 steps 6–7) needs the same handle. The URL is
  // written alongside so a refresh lands where the reviewer was (§1.1), and the
  // initial value comes from it so a shared link opens the right view.
  const [view, setView] = useState(
    parseReviewView(new URLSearchParams(window.location.search).get(VIEW_PARAM)),
  );
  const showView = (next: ReviewViewKey) => {
    setView(next);
    updateParams({ [VIEW_PARAM]: next });
  };

  // Preview is step 7; until it exists anything that is not Detail reads as
  // Overview, so a stale or hand-typed ?view=preview still renders a card.
  const isDetail = view === ReviewView.DETAIL;

  const cards = buildReviewCards({
    existing: pr_people?.existing ?? [],
    currentPeople: currentPeople ?? [],
    deletedIds,
    restoredIds,
    issues: review_data?.issues ?? [],
  });
  const frozen = useFrozenFields(requestId, cardFields(cards));

  // The modal walks the set it was opened from — from Overview, the group that
  // person was in. Stepping from To review into Unchanged would land on someone
  // with no visible fields, which is a dead end (§6).
  const [openPerson, setOpenPerson] = useState<{ id: string; field: string | null } | null>(null);
  const groups = groupCards(cards);
  const openCard = cards.find((c) => c.personId === openPerson?.id);
  const walkSet = !openCard
    ? []
    : needsReview(openCard)
      ? groups.toReview
      : groups.unchanged;

  const handleOpenPerson = (personId: string, fieldKey: string | null) =>
    setOpenPerson({ id: personId, field: fieldKey });

  // The modal renders the same rail Detail does, so both are built from one
  // definition — it is the rail mounted with one person, not a second editor.
  const railFor = (card: (typeof cards)[number]) =>
    railPropsFor(card, {
      frozen,
      dirtyIds,
      isReadOnly: !!is_read_only,
      jurisdictionOcdid,
      linkCandidates: linkCandidatesFrom(cards),
      // Everything is open in the modal: the reviewer went there to work on this
      // person, so hiding fields behind an expander would be in the way.
      expandedIds: new Set(cards.map((c) => c.personId)),
      onToggleExpand: () => {},
      onPersonSave: handlePersonSave,
      onDeletePerson: handleDeletePerson,
      onUndeletePerson: handleUndelete,
      onRestorePerson: handleRestore,
      onResetPerson: handleResetPerson,
    });


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
  // handleDelete takes a list — the jurisdiction table deletes in bulk; the
  // review card only ever drops the card in front of you.
  const handleDeletePerson = (id: string) => handleDelete([id]);

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
      <div class="review-page__views" role="tablist" aria-label="Review views">
        ${[ReviewView.OVERVIEW, ReviewView.DETAIL].map(
          (key) => html`<button
            class="review-page__view-tab ${view === key ? "review-page__view-tab--on" : ""}"
            role="tab"
            aria-selected=${view === key}
            @click=${() => showView(key)}
          >
            ${key === ReviewView.OVERVIEW ? "Overview" : "Detail"}
          </button>`,
        )}
      </div>
      ${!isDetail
        ? html`<review-overview
            .cards=${cards}
            .isReadOnly=${is_read_only}
            .onOpenPerson=${handleOpenPerson}
            .onAdd=${handleAdd}
          ></review-overview>`
        : html`<review-rail-list
            .cards=${cards}
            .frozen=${frozen}
            .requestId=${requestId}
            .dirtyIds=${dirtyIds}
            .isReadOnly=${is_read_only}
            .jurisdictionOcdid=${jurisdictionOcdid}
            .onPersonSave=${handlePersonSave}
            .onDeletePerson=${handleDeletePerson}
            .onUndeletePerson=${handleUndelete}
            .onRestorePerson=${handleRestore}
            .onResetPerson=${handleResetPerson}
            .onAdd=${handleAdd}
          ></review-rail-list>`}
      <review-modal
        .cards=${walkSet}
        .openPersonId=${openPerson?.id ?? null}
        .focusFieldKey=${openPerson?.field ?? null}
        .rail=${railFor}
        .deletedIds=${deletedIds}
        .restoredIds=${restoredIds}
        .onClose=${() => setOpenPerson(null)}
        .onPersonSave=${handlePersonSave}
        .onDelete=${handleDeletePerson}
        .onUndelete=${handleUndelete}
        .onRestore=${handleRestore}
        .onUndoRestore=${handleUndoRestore}
      ></review-modal>
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
