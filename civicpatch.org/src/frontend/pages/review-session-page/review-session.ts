import { html, nothing } from "lit-html";
import { component, useState } from "haunted";
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
import {
  blockingErrors,
  buildPersonCards,
  cardFields,
  duplicateIdsFor,
  needsReview,
  proposalsByPersonId,
  type PersonCard,
} from "../../components/people/person-cards.js";
import {
  personEditorPropsFor,
  type EditorContextBase,
} from "../../components/person-editor/editor-props.js";
import {
} from "../review-routes.js";
import { useJurisdictionPosts } from "../../hooks/use-jurisdiction-posts.js";
import { useJurisdictionRoles } from "../../hooks/use-jurisdiction-roles.js";
import "../../components/posts-list/post-add.js";
import type { ProposedChange } from "../../components/people/person-cards.js";
import type { PersonAssertion } from "../../components/person-editor/field-provenance.js";
import { jurisdictionOcdidToPath } from "../../components/ocdid-utils.js";

type CurrentEntry = {
  changeset_id: string;
  jurisdiction: {
    ocdid: string | null;
    name: string | null;
    path?: string | null;
    website_url?: string | null;
  };
  pr: {
    url: string | null;
    status: string | null;
    reviewState: string | null;
    number?: number | null;
  };
  mode: ReviewModeValue;
  pr_people: { existing: any[]; proposed: any[] };
  changes?: ProposedChange[];
  assertions?: Record<string, PersonAssertion[]>;
  review_data: any;
  source_content_urls: any[];
  is_read_only: boolean;
  has_next: boolean;
};

// Everything else is derived from `currentEntry`; these are what only the page knows.
type ReviewSessionHost = HTMLElement & {
  progress: Progress;
  hasSession: boolean;
  currentEntry: CurrentEntry | null;
  error: string | null;
  canReject: boolean;
  isRejecting: boolean;
};

/** The cards alike enough to page between: same review state, in roster order.
 *
 * Roster order so Prev / Next matches the list the modal was opened from, and same state
 * because stepping from someone with fields to review into someone with none is a dead end.
 * `needsReview` is the rule the views themselves split on.
 */
const peersOf = (
  openCard: PersonCard | undefined,
  cards: PersonCard[],
): PersonCard[] =>
  openCard
    ? cards.filter((card) => needsReview(card) === needsReview(openCard))
    : [];

function ReviewSession(host: ReviewSessionHost) {
  const { progress, hasSession, currentEntry, error, canReject, isRejecting } =
    host;
  const {
    jurisdiction,
    pr,
    mode,
    pr_people,
    changes,
    assertions,
    review_data,
    source_content_urls,
    is_read_only,
    has_next,
  } = currentEntry ?? ({} as Partial<CurrentEntry>);
  const {
    ocdid: jurisdictionOcdid,
    name: jurisdictionName,
    website_url: jurisdictionWebsiteUrl,
  } = jurisdiction ?? {};
  const { posts, reload: reloadPosts } = useJurisdictionPosts(jurisdictionOcdid);
  const roles = useJurisdictionRoles();
  // Which person asked for a post, so the one it creates can be picked for them.
  const [addingPostFor, setAddingPostFor] = useState<string | null>(null);
  const { url: publishedUrl, status: reviewStatus = null } = pr ?? {};
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
  const hasSourceContent = Boolean(
    source_content_urls && source_content_urls.length > 0,
  );

  const changesetId = currentEntry?.changeset_id ?? null;

  // Personal progress, so client-side — one key per card, which is why it needs a TTL.
  const allIssues = review_data?.issues ?? [];
  const [issueChecks, setIssueChecks] = useLocalStorage(
    issueChecksKey(changesetId ?? "none"),
    {},
    { ttl: ISSUE_CHECKS_TTL_MS },
  ) as [IssueChecks, (next: IssueChecks) => void];
  const handleToggleIssue = (issue: any) =>
    setIssueChecks(toggleCheck(issueChecks, issue));

  // Not persisted: landing on a card with a scrim already up is worse than reopening it.
  const [checklistOpen, setChecklistOpen] = useState(false);

  const cards = buildPersonCards({
    existing: pr_people?.existing ?? [],
    currentPeople: currentPeople ?? [],
    removedIds,
    restoredIds,
    // A tick has to clear the card's marker, or it does nothing where the reviewer is looking.
    issues: unresolvedIssues(allIssues, issueChecks),
    // A post is not a field, so the diff cannot see a move on its own.
    proposals: proposalsByPersonId(changes ?? []),
  });
  const frozen = useFrozenFields(changesetId, cardFields(cards));

  // Two people on one id collapse to a single entry, so one is on screen nowhere. Everything
  // downstream is keyed by person id, so keeping both is not an option; reporting it is.
  const duplicateIds = duplicateIdsFor({
    existing: pr_people?.existing ?? [],
    currentPeople: currentPeople ?? [],
  });

  // Same function fills Preview's banner, so the button and the banner cannot disagree.
  const blockers = blockingErrors(cards);

  const [openPerson, setOpenPerson] = useState<{
    id: string;
    field: string | null;
  } | null>(null);
  // Its own set, not Detail's: expanding in the modal is a different intent from expanding in
  // the list, and sharing would make one silently change the other.
  const [modalExpanded, setModalExpanded] = useState<Set<string>>(new Set());
  const openCard = cards.find((c) => c.personId === openPerson?.id);
  const modalCards = peersOf(openCard, cards);

  const handleOpenPerson = (personId: string, fieldKey: string | null) =>
    setOpenPerson({ id: personId, field: fieldKey });

  // The modal renders the same editor Detail does, so both are built from one
  // definition — it is the person editor mounted with one person, not a second one.
  const editorFor = (card: (typeof cards)[number]) =>
    personEditorPropsFor(card, {
      ...editorContext,
      isExpanded: (id: string) => modalExpanded.has(id),
      onToggleExpand: () => {
        const next = new Set(modalExpanded);
        next.has(card.personId)
          ? next.delete(card.personId)
          : next.add(card.personId);
        setModalExpanded(next);
      },
    });

  const handlePersonSave = (id: string, updates: Record<string, unknown>) =>
    updatePerson(id, updates);

  // Merge step 1 — picking who the same person is — renders inline on the editor, so only its
  // open/closed state lives here.
  const [candidatesOpenFor, setCandidatesOpenFor] = useState<string | null>(null);
  const handleToggleCandidates = (personId: string) =>
    setCandidatesOpenFor((current) => (current === personId ? null : personId));

  // Step 2 is the modal's other screen, not a second dialog — so merge always has a person
  // behind it and "back" always has somewhere to go.
  const [pendingMerge, setPendingMerge] = useState<{
    anchorId: string;
    partnerId: string;
  } | null>(null);
  const handlePickPartner = (anchorId: string, partnerId: string) => {
    setCandidatesOpenFor(null);
    setPendingMerge({ anchorId, partnerId });
    setOpenPerson({ id: anchorId, field: null });
  };
  const clearPendingMerge = () => setPendingMerge(null);

  // The picker owns the policy; this only carries its result through.
  const handleMergePeople = (
    survivorId: string,
    absorbedId: string,
    merged: Record<string, unknown>,
  ) => {
    setPendingMerge(null);
    mergePeople(survivorId, absorbedId, merged);
    // Follow the survivor: the absorbed id is gone, so leaving it open renders no card
    // and the modal vanishes — dropping the reviewer to the roster just as the merged
    // record needs checking.
    setOpenPerson({ id: survivorId, field: null });
  };
  const handleAddPerson = async () => {
    const personId = await handleAdd();
    setOpenPerson({ id: personId, field: null });
  };

  const handleResetPerson = (id: string) => handleReset(id);
  // `handleRemove` takes a list because the jurisdiction table deletes in bulk.
  const handleRemovePerson = (id: string) => handleRemove([id]);

  const editorContext: EditorContextBase = {
    frozen,
    dirtyIds,
    isReadOnly: !!is_read_only,
    jurisdictionOcdid,
    posts,
    proposals: proposalsByPersonId(changes ?? []),
    assertions: assertions ?? {},
    onPersonSave: handlePersonSave,
    onRemovePerson: handleRemovePerson,
    onUnremovePerson: handleUnremove,
    onRestorePerson: handleRestore,
    onResetPerson: handleResetPerson,
    cards,
    candidatesOpenFor,
    onToggleCandidates: handleToggleCandidates,
    onPickPartner: handlePickPartner,
    onAddPost: setAddingPostFor,
  };

  // The post the form just made becomes this person's pick — the reviewer opened it to
  // answer the Post field, so leaving them to find it in a reloaded select is half the job.
  const handlePostAdded = (e: CustomEvent) => {
    const postId = e.detail?.post_id;
    if (addingPostFor && postId) handlePersonSave(addingPostFor, { post_id: postId });
    setAddingPostFor(null);
    reloadPosts();
  };

  return html`
    <main class="review-page">
      ${addingPostFor
        ? html`<civ-post-add
            .jurisdictionOcdid=${jurisdictionOcdid ?? ""}
            .roles=${roles}
            @added=${handlePostAdded}
            @cancel=${() => setAddingPostFor(null)}
          ></civ-post-add>`
        : ""}
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
          .canReject=${canReject}
          .isRejecting=${isRejecting}
          .hasSession=${hasSession}
        ></review-session-actions>
      </div>
      <!-- Notices come before the jurisdiction, not after it: each one changes
           what publishing this card will do, so it has to be read before the
           card is. -->
      ${error ? html`<p class="review-page__error">${error}</p>` : ""}
      ${is_read_only
        ? html`<div
            class="review-page__status-banner review-page__status-banner--${reviewStatus}"
          >
            ${reviewStatus}
          </div>`
        : ""}
      ${duplicateIds.length
        ? html`<div class="review-page__duplicate-banner">
            <strong>
              ${duplicateIds.length}
              record${duplicateIds.length === 1 ? "" : "s"} share an id with
              another on this card.
            </strong>
            Only one of each pair is shown, and publishing will send only that
            one. Ids: ${duplicateIds.join(", ")}.
          </div>`
        : nothing}
      ${isBaseline
        ? html`<div class="review-page__baseline-banner">
            <strong
              >First capture for
              ${jurisdictionName ?? "this jurisdiction"}.</strong
            >
            Nothing to compare against yet — publishing creates these records
            for the first time.
          </div>`
        : ""}
      <div class="review-page__info-row">
        <div class="review-page__pr-meta">
          ${jurisdictionName
            ? html`<a
                class="review-page__jurisdiction"
                href="/${jurisdictionOcdidToPath(jurisdiction?.path)}"
                target="_blank"
                rel="noopener"
              >
                ${jurisdictionName}
                <i class="fa-solid fa-arrow-up-right-from-square"></i>
              </a>`
            : ""}
          ${jurisdictionWebsiteUrl
            ? html`<a
                class="review-page__jurisdiction-website"
                href=${jurisdictionWebsiteUrl}
                target="_blank"
                rel="noopener"
              >
                ${jurisdictionWebsiteUrl}
                <i class="fa-solid fa-arrow-up-right-from-square"></i>
              </a>`
            : ""}
          ${publishedUrl
            ? html`<a
                class="btn btn-sm"
                href=${publishedUrl}
                target="_blank"
                rel="noopener"
                >View published data
                <i class="fa-solid fa-arrow-up-right-from-square"></i
              ></a>`
            : ""}
          ${hasSourceContent
            ? html`<button
                class="btn btn-sm secondary"
                @click=${() => setDebugOpen(true)}
              >
                Debug
              </button>`
            : ""}
          <report-issue-button
            .changesetId=${changesetId}
          ></report-issue-button>
        </div>
      </div>
      <review-overview
        .cards=${cards}
        .changes=${changes}
        .isReadOnly=${is_read_only}
        .onOpenPerson=${handleOpenPerson}
        .onAdd=${handleAddPerson}
      ></review-overview>
      <!-- Not a tab: what will be published is the same question as what changed, and a
           reviewer had to remember to go and look. It reads after the roster because it is
           the consequence of it. -->
      <section class="review-page__publishing" aria-label="Preview">
        <h2 class="review-page__section-title">Preview</h2>
        <review-preview
          .changes=${changes}
          .cards=${cards}
          .jurisdictionOcdid=${jurisdictionOcdid}
          .onOpenPerson=${handleOpenPerson}
        ></review-preview>
      </section>
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
        .changes=${changes}
        .cards=${modalCards}
        .openPersonId=${openPerson?.id ?? null}
        .focusFieldKey=${openPerson?.field ?? null}
        .editor=${editorFor}
        .isReadOnly=${!!is_read_only}
        .onClose=${() => setOpenPerson(null)}
        .mergePartner=${pendingMerge
          ? (cards.find((c) => c.personId === pendingMerge.partnerId) ?? null)
          : null}
        .onMergeBack=${clearPendingMerge}
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
