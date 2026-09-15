
import { html, nothing } from "lit-html";
import { component, useState, useEffect, useCallback } from "haunted";
import "./jurisdiction-page.css";
import {
  patchPeopleData,
  generatePersonId,
  assignMembership,
} from "../../api.js";
import { fetchPeopleAssertions } from "../../api.js";
import { usePeopleState } from "../../components/edit-people/hooks/use-people-state.js";
import { emptyPerson } from "../../components/edit-people/people-editing.js";
import {
  blockingErrors,
  buildPersonCards,
  navHintFor,
  type PersonCard,
} from "../../components/people/person-cards.js";
import { personEditorPropsFor } from "../../components/person-editor/editor-props.js";
import { focusOnMount } from "../../utils/focus-on-mount.js";
import { EMPTY_FROZEN } from "../review-session-page/frozen-fields.js";
import { renderRosterCards } from "./roster-section.js";
import { useOrganizations } from "../../hooks/use-organizations.js";
import { useJurisdictionRoles } from "../../hooks/use-jurisdiction-roles.js";
import { useAltArrowPeerNav } from "../../hooks/use-alt-arrow-peer-nav.js";
import { officeChangesIn } from "../../components/person-editor/office-changes.js";
import {
  cardOrganizationsById,
  groupCardsByOrganization,
} from "./roster-organization-grouping.js";

interface RosterEditorProps {
  people: any[];
  jurisdictionOcdid: string;
  canEdit: boolean;
  canAssignMembership: boolean;
  canCreatePost: boolean;
  isLoading: boolean;
  blockedReason: string | null;
  onPublished: () => void;
}

type PublishStage = "idle" | "publishing";

function publishLabel(blockerCount: number, stage: PublishStage): string {
  if (blockerCount) return `${blockerCount} to fix before publishing`;
  if (stage === "publishing") return "Publishing…";
  return "Publish changes";
}

function RosterEditor({
  people,
  jurisdictionOcdid,
  canEdit,
  canAssignMembership,
  canCreatePost,
  isLoading,
  blockedReason,
  onPublished,
}: RosterEditorProps) {
  const { organizations } = useOrganizations(jurisdictionOcdid);
  const roles = useJurisdictionRoles();
  // Where "Add" was clicked for a not-yet-saved person, since they hold no post yet to place
  // them by. Session-local — once they're given an office their held post takes over.
  const [addedUnderOrg, setAddedUnderOrg] = useState<Map<string, string>>(new Map());
  const published = people ?? [];
  const state = usePeopleState({ people: published });
  const {
    currentPeople,
    removedIds,
    restoredIds,
    dirtyIds,
    dirty,
    peoplePatch,
    assignPeople,
    addPerson,
    updatePerson,
    handleRemove,
    handleUnremove,
    handleRestore,
    handleReset,
    handleResetAll,
  } = state;
  const [openPersonId, setOpenPersonId] = useState<string | null>(null);
  const [focusFieldKey, setFocusFieldKey] = useState<string | null>(null);
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());
  const [publishStage, setPublishStage] = useState<PublishStage>("idle");
  const [publishError, setPublishError] = useState<string | null>(null);
  const isPublishing = publishStage !== "idle";
  useEffect(() => {
    assignPeople(published);
  }, [people]);
  const [assertions, setAssertions] = useState<Record<string, any[]>>({});
  useEffect(() => {
    if (!canEdit || !jurisdictionOcdid) return;
    fetchPeopleAssertions(jurisdictionOcdid)
      .then((body) => setAssertions(body.data ?? {}))
      .catch(() => setAssertions({}));
  }, [jurisdictionOcdid, canEdit]);
  const cards: PersonCard[] = buildPersonCards({
    existing: published,
    currentPeople: currentPeople ?? [],
    removedIds,
    restoredIds,
    issues: [],
  });
  const blockers = blockingErrors(cards);
  const blockerTitle = blockers
    .map((blocker) => `${blocker.name}, ${blocker.fieldLabel}: ${blocker.message}`)
    .join("\n");
  // Same mechanism as review-session.ts: alt-arrow steps to the next/previous card while
  // one is open, and the opened field autofocuses once the inline editor has mounted.
  const handleOpenPerson = (personId: string, fieldKey: string | null) => {
    const opening = openPersonId !== personId;
    setOpenPersonId(opening ? personId : null);
    setFocusFieldKey(opening ? fieldKey : null);
  };
  useAltArrowPeerNav(openPersonId, cards, (next) => {
    setOpenPersonId(next.personId);
    setFocusFieldKey(null);
  });
  const focusOnOpen = useCallback(focusOnMount, [focusFieldKey]);
  const handlePersonSave = (id: string, updates: Record<string, unknown>) =>
    updatePerson(id, updates);
  const handleAdd = async (organizationId: string) => {
    const personId = await generatePersonId();
    setAddedUnderOrg((current) => new Map(current).set(personId, organizationId));
    addPerson(emptyPerson(personId, jurisdictionOcdid));
    handleOpenPerson(personId, null);
  };
  const handlePublish = async () => {
    setPublishStage("publishing");
    setPublishError(null);
    try {
      // Office picks first: direct writes, unrelated to the PR this patch opens, but both
      // are "make what's on screen real" and belong behind the one button that says so.
      for (const change of officeChangesIn(cards)) {
        await assignMembership(change.personId, change.postId, change.label);
      }
      await patchPeopleData(jurisdictionOcdid, peoplePatch);
      onPublished();
    } catch (err: any) {
      setPublishError(err.message ?? "Failed to publish.");
      setPublishStage("idle");
    }
  };
  const groups = groupCardsByOrganization(cards, organizations, addedUnderOrg);
  const cardOrganizations = cardOrganizationsById(groups);
  const editorFor = (card: PersonCard) => {
    const cardOrganization = cardOrganizations.get(card.personId);
    const base = personEditorPropsFor(card, {
      frozen: EMPTY_FROZEN,
      dirtyIds,
      isReadOnly: !canEdit,
      jurisdictionOcdid,
      posts: cardOrganization?.posts ?? [],
      organizationId: cardOrganization?.organizationId ?? "",
      roles,
      canAssignMembership,
      canCreatePost,
      proposals: new Map(),
      assertions,
      overriddenSourceValues: {},
      isExpanded: (id: string) => !collapsedIds.has(id),
      onToggleExpand: () => {
        const next = new Set(collapsedIds);
        next.has(card.personId) ? next.delete(card.personId) : next.add(card.personId);
        setCollapsedIds(next);
      },
      onPersonSave: handlePersonSave,
      onRemovePerson: (id: string) => handleRemove([id]),
      onUnremovePerson: handleUnremove,
      onRestorePerson: handleRestore,
      onResetPerson: handleReset,
      cards: [],
      candidatesOpenFor: false,
      onToggleCandidates: () => {},
      onPickPartner: () => {},
    });
    return {
      ...base,
      navHint: navHintFor(cards, card.personId),
      focusField:
        card.personId === openPersonId && focusFieldKey
          ? { key: focusFieldKey, attach: focusOnOpen }
          : null,
    };
  };
  // Add is per-organization — it's the section whose Add button placed a new person that
  // decides which body they're minted under. Discard/Publish stay shared: one dirty roster,
  // one PR, across every organization's cards.
  const addActionFor = (organizationId: string) =>
    canEdit
      ? html`<button
          class="btn-quiet"
          ?disabled=${isPublishing}
          @click=${() => handleAdd(organizationId)}
        >
          <i class="fa-solid fa-plus"></i> Add
        </button>`
      : nothing;
  const toolbar =
    canEdit && dirty
      ? html`
          <div class="roster-toolbar">
            <button class="btn-quiet" ?disabled=${isPublishing} @click=${handleResetAll}>Discard</button>
            <button
              class="btn-primary"
              ?disabled=${isPublishing || blockers.length > 0}
              title=${blockers.length ? blockerTitle : ""}
              @click=${handlePublish}
            >
              ${publishLabel(blockers.length, publishStage)}
            </button>
          </div>
        `
      : nothing;
  return html`
    ${toolbar}
    ${groups.map(
      (group) => html`
        ${renderRosterCards({
          cards: group.cards,
          isLoading,
          blockedReason,
          actions: addActionFor(group.organization.id),
          onOpenPerson: canEdit ? handleOpenPerson : null,
          openPersonId: canEdit ? openPersonId : null,
          editorFor: canEdit ? editorFor : null,
          roles,
          title: group.organization.name,
        })}
      `,
    )}
    ${publishError
      ? html`<p style="color: var(--diff-removed);">${publishError}</p>`
      : nothing}
  `;
}

customElements.define(
  "civ-roster-editor",
  component(RosterEditor as any, { useShadowDOM: false }),
);
