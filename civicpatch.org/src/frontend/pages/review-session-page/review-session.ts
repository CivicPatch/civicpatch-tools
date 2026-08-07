import { html, nothing } from "lit-html";
import { component, useState } from "haunted";
import "../../components/person-editor/person-editor-list.js";
import "../../components/review-overview/review-overview.js";
import "../../components/review-preview/review-preview.js";
import "../../components/review/review-modal.js";
import "../../components/review-sidebar/review-sidebar.js";
import { checkedCount } from "../../components/review-sidebar/sidebar-model.js";
import "../../components/source-content/source-content-debug-modal.js";
import { type Progress } from "./review-session-controls.js";
import "./review-session-controls.js";
import "./review-session-actions.js";
import "./report-issue-button.js";
import { useReviewPeople } from "./use-review-people.js";
import { updateParams } from "./use-review-session.js";
import { useLocalStorage } from "../../hooks/use-local-storage.js";
import {
  issueChecksKey,
  toggleCheck,
  unresolvedIssues,
  ISSUE_CHECKS_TTL_MS,
  type IssueChecks,
} from "../../components/review/issue-checks.js";
import { useFrozenFields } from "./use-frozen-fields.js";
import { ReviewMode, type ReviewModeValue } from "./review-state.js";
import { blockingErrors, buildReviewCards, cardFields, duplicateIdsFor, needsReview } from "../../components/review/review-cards.js";
import { personEditorPropsFor } from "../../components/person-editor/editor-props.js";
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
    removedIds,
    restoredIds,
    dirty,
    peoplePatch,
    handleAdd,
    handleReset,
    handleRemove,
    handleUnremove,
    handleRestore,
    updatePerson,
    mergePeople,
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

  // Ticks are personal progress in this browser, so they persist client-side.
  // Unlike the app's other stored values there is one key per card, so they age
  // out rather than accumulating forever.
  const allIssues = review_data?.issues ?? [];
  const [issueChecks, setIssueChecks] = useLocalStorage(
    issueChecksKey(requestId ?? "none"),
    {},
    { ttl: ISSUE_CHECKS_TTL_MS },
  ) as [IssueChecks, (next: IssueChecks) => void];
  const handleToggleIssue = (issue: any) =>
    setIssueChecks(toggleCheck(issueChecks, issue));

  // The drawer is transient — the trigger lives outside it, so the page holds
  // the one boolean. Deliberately not persisted: landing on a card with a scrim
  // already up would be worse than reopening it.
  const [checklistOpen, setChecklistOpen] = useState(false);

  const cards = buildReviewCards({
    existing: pr_people?.existing ?? [],
    currentPeople: currentPeople ?? [],
    removedIds,
    restoredIds,
    // A ticked issue is done, so it stops marking its card — otherwise the tick
    // would have no effect where the reviewer was actually looking (§8.2).
    issues: unresolvedIssues(allIssues, issueChecks),
  });
  const frozen = useFrozenFields(requestId, cardFields(cards));

  // Two scraped people resolving to one id collapse into a single diff entry —
  // last wins — so one of them is on screen nowhere. Everything downstream is
  // keyed by person id, so keeping both is not an option; saying so is (§21.8).
  const duplicateIds = duplicateIdsFor({
    existing: pr_people?.existing ?? [],
    currentPeople: currentPeople ?? [],
  });

  // Publish is gated by the same function that fills Preview's banner — one
  // rule, two consumers, so the button and the banner can never disagree about
  // whether the card is publishable (§9).
  const blockers = blockingErrors(cards);

  // The modal walks the roster in the order the views render it, so stepping
  // through people matches the list you opened the modal from. groupCards sorts
  // by status and would step you through a different sequence than the one on
  // screen (§3, §6).
  //
  // It still walks only people in the same state as the one you opened —
  // stepping from someone with fields to review into someone with none is a
  // dead end, and needsReview is the same rule the views split on.
  const [openPerson, setOpenPerson] = useState<{ id: string; field: string | null } | null>(null);
  // The modal collapses unchanged fields exactly as Detail does. It has its own
  // set rather than sharing Detail's: expanding someone in the modal is a
  // different intent from expanding them in the list, and sharing would make one
  // silently change the other.
  const [modalExpanded, setModalExpanded] = useState<Set<string>>(new Set());
  const openCard = cards.find((c) => c.personId === openPerson?.id);
  const walkSet = !openCard
    ? []
    : cards.filter((card) => needsReview(card) === needsReview(openCard));

  const handleOpenPerson = (personId: string, fieldKey: string | null) =>
    setOpenPerson({ id: personId, field: fieldKey });

  // The modal renders the same editor Detail does, so both are built from one
  // definition — it is the person editor mounted with one person, not a second one.
  const editorFor = (card: (typeof cards)[number]) =>
    personEditorPropsFor(card, {
      frozen,
      dirtyIds,
      isReadOnly: !!is_read_only,
      jurisdictionOcdid,
      isExpanded: (id: string) => modalExpanded.has(id),
      onToggleExpand: () => {
        const next = new Set(modalExpanded);
        next.has(card.personId)
          ? next.delete(card.personId)
          : next.add(card.personId);
        setModalExpanded(next);
      },
      onPersonSave: handlePersonSave,
      onRemovePerson: handleRemovePerson,
      onUnremovePerson: handleUnremove,
      onRestorePerson: handleRestore,
      onResetPerson: handleResetPerson,
      cards,
      mergeOpenId,
      onToggleMerge: handleToggleMerge,
      onPickPartner: handlePickPartner,
    });


  const handlePersonSave = (id: string, updates: Record<string, unknown>) => updatePerson(id, updates);

  // One person, two records. The policy is merge-model's; usePeopleState owns
  // only what happens to the rows. Link reaches this with the defaults
  // untouched, and the picker will reach it with an edited plan.
  // Step 1 of a merge: which record is the same person? The anchor is the row
  // the reviewer invoked it from; the picker computes the survivor.
  // Step 1 lives inline on the editor, so only its open/closed state is held here.
  const [mergeOpenId, setMergeOpenId] = useState<string | null>(null);
  const handleToggleMerge = (personId: string) =>
    setMergeOpenId((current) => (current === personId ? null : personId));

  // Step 2 is the modal's other screen, not a second dialog. Picking a partner from
  // Detail opens the anchor's modal on it, so merge always has a person behind it
  // and "back" always has somewhere to go.
  const [mergePair, setMergePair] = useState<{ anchorId: string; partnerId: string } | null>(null);
  const handlePickPartner = (anchorId: string, partnerId: string) => {
    setMergeOpenId(null);
    setMergePair({ anchorId, partnerId });
    setOpenPerson({ id: anchorId, field: null });
  };
  const closeMergePicker = () => setMergePair(null);

  // The picker owns the policy — it holds the plan the reviewer edited — so this
  // only carries the result through to the list.
  const handleMergePeople = (
    survivorId: string,
    absorbedId: string,
    merged: Record<string, unknown>,
  ) => {
    setMergePair(null);
    mergePeople(survivorId, absorbedId, merged);
  };
  // A new person is empty, so land the reviewer in the editor rather than on a card
  // with nothing on it.
  const handleAddPerson = async () => {
    const personId = await handleAdd();
    setOpenPerson({ id: personId, field: null });
  };

  const handleResetPerson = (id: string) => handleReset(id);
  // handleRemove takes a list — the jurisdiction table deletes in bulk; the
  // review card only ever drops the card in front of you.
  const handleRemovePerson = (id: string) => handleRemove([id]);

  return html`
    <main class="review-page">
      <div class="review-page__header">
        <review-session-controls
          .progress=${progress}
          .hasSession=${hasSession}
          .hasNext=${has_next}
          .checklistDone=${checkedCount(allIssues, issueChecks)}
          .checklistTotal=${allIssues.length}
          @checklist-open=${() => setChecklistOpen(true)}
        ></review-session-controls>
        <review-session-actions
          .isReadOnly=${!!is_read_only}
          .dirty=${dirty}
          .peoplePatch=${peoplePatch}
          .blockers=${blockers}
          .canClosePr=${canClosePr}
          .isClosingPr=${isClosingPr}
          .hasSession=${hasSession}
        ></review-session-actions>
      </div>
      <!-- Notices come before the jurisdiction, not after it: each one changes
           what publishing this card will do, so it has to be read before the
           card is. -->
      ${error ? html`<p class="review-page__error">${error}</p>` : ""}
      ${is_read_only ? html`<div class="review-page__status-banner review-page__status-banner--${pullRequestStatus}">${pullRequestStatus}</div>` : ""}
      ${duplicateIds.length
        ? html`<div class="review-page__duplicate-banner">
            <strong>
              ${duplicateIds.length} record${duplicateIds.length === 1 ? "" : "s"}
              share an id with another on this card.
            </strong>
            Only one of each pair is shown, and publishing will send only that
            one. Ids: ${duplicateIds.join(", ")}.
          </div>`
        : nothing}
      ${isBaseline
        ? html`<div class="review-page__baseline-banner">
            <strong>First capture for ${jurisdictionName ?? "this jurisdiction"}.</strong>
            Nothing to compare against yet — publishing creates these records for
            the first time.
          </div>`
        : ""}
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
      </div>
      <div class="review-page__views" role="tablist" aria-label="Review views">
        ${[
          [ReviewView.OVERVIEW, "Overview"],
          [ReviewView.DETAIL, "Detail"],
          [ReviewView.PREVIEW, "Preview"],
        ].map(
          ([key, label]) => html`<button
            class="review-page__view-tab ${view === key ? "review-page__view-tab--on" : ""}"
            role="tab"
            aria-selected=${view === key}
            @click=${() => showView(key as ReviewViewKey)}
          >
            ${label}
          </button>`,
        )}
      </div>
      ${view === ReviewView.PREVIEW
        ? html`<review-preview
            .cards=${cards}
            .jurisdictionOcdid=${jurisdictionOcdid}
            .onOpenPerson=${handleOpenPerson}
          ></review-preview>`
        : view !== ReviewView.DETAIL
        ? html`<review-overview
            .cards=${cards}
            .isReadOnly=${is_read_only}
            .onOpenPerson=${handleOpenPerson}
            .onAdd=${handleAddPerson}
          ></review-overview>`
        : html`<person-editor-list
            .cards=${cards}
            .frozen=${frozen}
            .requestId=${requestId}
            .dirtyIds=${dirtyIds}
            .isReadOnly=${is_read_only}
            .jurisdictionOcdid=${jurisdictionOcdid}
            .onPersonSave=${handlePersonSave}
            .onRemovePerson=${handleRemovePerson}
            .onUnremovePerson=${handleUnremove}
            .onRestorePerson=${handleRestore}
            .onResetPerson=${handleResetPerson}
            .mergeOpenId=${mergeOpenId}
            .onToggleMerge=${handleToggleMerge}
            .onPickPartner=${handlePickPartner}
            .onAdd=${handleAddPerson}
          ></person-editor-list>`}
      <review-sidebar
        .issues=${allIssues}
        .checks=${issueChecks}
        .peopleBySource=${review_data?.people_by_source ?? []}
        .originSource=${review_data?.origin_source ?? null}
        .open=${checklistOpen}
        @close=${() => setChecklistOpen(false)}
        @toggle-issue=${(e: CustomEvent) => handleToggleIssue(e.detail.issue)}
      ></review-sidebar>
      <review-modal
        .cards=${walkSet}
        .openPersonId=${openPerson?.id ?? null}
        .focusFieldKey=${openPerson?.field ?? null}
        .editor=${editorFor}
        .isReadOnly=${!!is_read_only}
        .onClose=${() => setOpenPerson(null)}
        .mergePartner=${mergePair
          ? (cards.find((c) => c.personId === mergePair.partnerId) ?? null)
          : null}
        .onMergeBack=${closeMergePicker}
        .onMerge=${handleMergePeople}
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
