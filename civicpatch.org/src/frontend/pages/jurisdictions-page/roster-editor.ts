
import { html, nothing } from "lit-html";
import { component, useState, useEffect, useCallback, useRef } from "haunted";
import "./jurisdiction-page.css";
import "../../components/status-toast/status-toast.js";
import "../../components/status-toast/status-toast.css";
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
import { useRosterMemberships } from "../../hooks/use-roster-memberships.js";
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

const TOAST_TIMEOUT_MS = 10_000;

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
  const { organizations, reload: reloadOrganizations } = useOrganizations(jurisdictionOcdid);
  // No changeset: this page edits live data, so a claim applies to the published roster as soon
  // as the next publish re-derives it.
  const { memberships, setRemoval, setNotAMemberHere } =
    useRosterMemberships(jurisdictionOcdid);
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
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<number | null>(null);
  useEffect(() => {
    return () => {
      if (toastTimer.current !== null) window.clearTimeout(toastTimer.current);
    };
  }, []);
  const dismissToast = () => {
    if (toastTimer.current !== null) {
      window.clearTimeout(toastTimer.current);
      toastTimer.current = null;
    }
    setToast(null);
  };
  const showToast = (message: string) => {
    if (toastTimer.current !== null) window.clearTimeout(toastTimer.current);
    setToast(message);
    toastTimer.current = window.setTimeout(() => {
      setToast(null);
      toastTimer.current = null;
    }, TOAST_TIMEOUT_MS);
  };
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
      setOpenPersonId(null);
      setFocusFieldKey(null);
      setPublishStage("idle");
      showToast("Changes published.");
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
      rosterMemberships: memberships,
      onSetRemoval: setRemoval,
      onSetNotAMember: setNotAMemberHere,
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
  // Always present once editing is allowed — not just while dirty — so Discard/Publish never
  // pop in and out of the layout; disabling them says the same thing without the jump.
  const header = canEdit
    ? html`
        <div class="panel roster-header">
          <div class="panel__cap">
            <b>Roster</b>
            <span class="panel__cap-right roster-toolbar">
              ${toast
                ? html`<status-toast
                    .message=${toast}
                    .onDismiss=${dismissToast}
                  ></status-toast>`
                : nothing}
              <button
                class="btn-quiet"
                ?disabled=${!dirty || isPublishing}
                @click=${handleResetAll}
              >
                Discard
              </button>
              <button
                class="btn-primary"
                ?disabled=${!dirty || isPublishing || blockers.length > 0}
                title=${blockers.length ? blockerTitle : ""}
                @click=${handlePublish}
              >
                ${publishLabel(blockers.length, publishStage)}
              </button>
            </span>
          </div>
          ${publishError
            ? html`<p style="color: var(--diff-removed);">${publishError}</p>`
            : nothing}
        </div>
      `
    : nothing;
  return html`
    <div @post-created=${reloadOrganizations}>
      ${header}
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
    </div>
  `;
}

customElements.define(
  "civ-roster-editor",
  component(RosterEditor as any, { useShadowDOM: false }),
);
