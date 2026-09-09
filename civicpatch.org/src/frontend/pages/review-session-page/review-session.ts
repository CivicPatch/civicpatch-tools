import { html, nothing } from "lit-html";
import { component, useState, useEffect, useCallback } from "haunted";
import "../../components/review-overview/review-overview.js";
import "../../components/review-preview/review-preview.js";
import "../../components/review/review-modal.js";
import "../../components/review-sidebar/review-sidebar.js";
import { checkedCount } from "../../components/review-sidebar/sidebar-model.js";
import { focusOnMount } from "../../utils/focus-on-mount.js";
import { altArrowDirection, isTyping } from "../../utils/keyboard.js";
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
  adjacentPeer,
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
import {
  jurisdictionOcdidToPath,
  jurisdictionOcdidToState,
  stateNameForCode,
} from "../../components/ocdid-utils.js";

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
  overriddenSourceValues?: Record<string, Record<string, unknown>>;
  review_data: any;
  source_content_urls: any[];
  is_read_only: boolean;
  has_next: boolean;
};

type ReviewSessionHost = HTMLElement & {
  progress: Progress;
  hasSession: boolean;
  currentEntry: CurrentEntry | null;
  error: string | null;
  canReject: boolean;
  isRejecting: boolean;
};

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
    overriddenSourceValues,
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
  const jurisdictionStateName = stateNameForCode(
    jurisdictionOcdidToState(jurisdictionOcdid ?? ""),
  );
  const jurisdictionTitle = jurisdictionStateName
    ? `${jurisdictionName}, ${jurisdictionStateName}`
    : jurisdictionName;
  const { posts, reload: reloadPosts } = useJurisdictionPosts(jurisdictionOcdid);
  const roles = useJurisdictionRoles();
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
  const allIssues = review_data?.issues ?? [];
  const [issueChecks, setIssueChecks] = useLocalStorage(
    issueChecksKey(changesetId ?? "none"),
    {},
    { ttl: ISSUE_CHECKS_TTL_MS },
  ) as [IssueChecks, (next: IssueChecks) => void];
  const handleToggleIssue = (issue: any) =>
    setIssueChecks(toggleCheck(issueChecks, issue));
  const [checklistOpen, setChecklistOpen] = useState(false);
  const cards = buildPersonCards({
    existing: pr_people?.existing ?? [],
    currentPeople: currentPeople ?? [],
    removedIds,
    restoredIds,
    issues: unresolvedIssues(allIssues, issueChecks),
    proposals: proposalsByPersonId(changes ?? []),
  });
  const frozen = useFrozenFields(changesetId, cardFields(cards));
  const duplicateIds = duplicateIdsFor({
    existing: pr_people?.existing ?? [],
    currentPeople: currentPeople ?? [],
  });
  const blockers = blockingErrors(cards);
  const [openPersonId, setOpenPersonId] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const [focusFieldKey, setFocusFieldKey] = useState<string | null>(null);
  const openCard = cards.find((c) => c.personId === openPersonId);
  const openPeers = peersOf(openCard, cards);
  const handleOpenPerson = (personId: string, fieldKey: string | null) => {
    const opening = openPersonId !== personId;
    setOpenPersonId(opening ? personId : null);
    setFocusFieldKey(opening ? fieldKey : null);
  };
  useEffect(() => {
    if (!openPersonId) return;
    const onKey = (e: KeyboardEvent) => {
      const direction = altArrowDirection(e);
      if (!direction || isTyping(document.activeElement)) return;
      const nextCard = adjacentPeer(openPeers, openPersonId, direction);
      if (!nextCard) return;
      e.preventDefault();
      setOpenPersonId(nextCard.personId);
      setFocusFieldKey(null);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [openPersonId, openPeers]);
  const focusOnOpen = useCallback(focusOnMount, [focusFieldKey]);
  const editorFor = (card: (typeof cards)[number]) => {
    const base = personEditorPropsFor(card, {
      ...editorContext,
      isExpanded: (id: string) => expandedIds.has(id),
      onToggleExpand: () => {
        const next = new Set(expandedIds);
        next.has(card.personId)
          ? next.delete(card.personId)
          : next.add(card.personId);
        setExpandedIds(next);
      },
    });
    const peers = card.personId === openPersonId ? openPeers : peersOf(card, cards);
    const peerIndex = peers.findIndex((c) => c.personId === card.personId);
    return {
      ...base,
      navHint:
        peers.length > 1
          ? { hasPrev: peerIndex > 0, hasNext: peerIndex < peers.length - 1 }
          : undefined,
      focusField:
        card.personId === openPersonId && focusFieldKey
          ? { key: focusFieldKey, attach: focusOnOpen }
          : null,
    };
  };
  const handlePersonSave = (id: string, updates: Record<string, unknown>) =>
    updatePerson(id, updates);
  const [candidatesOpen, setCandidatesOpen] = useState(false);
  const handleToggleCandidates = () => setCandidatesOpen((open) => !open);
  const [pendingMerge, setPendingMerge] = useState<{
    anchorId: string;
    partnerId: string;
  } | null>(null);
  const mergeAnchorId = pendingMerge?.anchorId ?? null;
  const handlePickPartner = (anchorId: string, partnerId: string) => {
    setCandidatesOpen(false);
    setPendingMerge({ anchorId, partnerId });
  };
  const clearPendingMerge = () => setPendingMerge(null);
  const handleMergePeople = (
    survivorId: string,
    absorbedId: string,
    merged: Record<string, unknown>,
  ) => {
    setPendingMerge(null);
    mergePeople(survivorId, absorbedId, merged);
    handleOpenPerson(survivorId, null);
  };
  const handleAddPerson = async () => {
    const personId = await handleAdd();
    handleOpenPerson(personId, null);
  };
  const handleResetPerson = (id: string) => handleReset(id);
  const handleRemovePerson = (id: string) => handleRemove([id]);
  const editorContext: EditorContextBase = {
    frozen,
    dirtyIds,
    isReadOnly: !!is_read_only,
    jurisdictionOcdid,
    posts,
    proposals: proposalsByPersonId(changes ?? []),
    assertions: assertions ?? {},
    overriddenSourceValues: overriddenSourceValues ?? {},
    onPersonSave: handlePersonSave,
    onRemovePerson: handleRemovePerson,
    onUnremovePerson: handleUnremove,
    onRestorePerson: handleRestore,
    onResetPerson: handleResetPerson,
    cards,
    candidatesOpenFor: candidatesOpen,
    onToggleCandidates: handleToggleCandidates,
    onPickPartner: handlePickPartner,
    onAddPost: setAddingPostFor,
  };
  const handlePostAdded = (e: CustomEvent) => {
    const postId = e.detail?.post_id;
    if (addingPostFor && postId) handlePersonSave(addingPostFor, { post_id: postId });
    setAddingPostFor(null);
    reloadPosts();
  };
  return html`
    <main class="review-page page-content">
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
                ${jurisdictionTitle}
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
        .openPersonId=${openPersonId}
        .editorFor=${editorFor}
        .posts=${posts}
        .assertions=${assertions ?? {}}
        .overriddenSourceValues=${overriddenSourceValues ?? {}}
      ></review-overview>
      <section class="review-page__publishing" aria-label="Preview">
        <h2 class="review-page__section-title">Preview</h2>
        <review-preview
          .changes=${changes}
          .cards=${cards}
          .jurisdictionOcdid=${jurisdictionOcdid}
          .posts=${posts}
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
        .cards=${cards}
        .posts=${posts}
        .openPersonId=${mergeAnchorId}
        .focusFieldKey=${null}
        .editor=${editorFor}
        .isReadOnly=${!!is_read_only}
        .onClose=${clearPendingMerge}
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
