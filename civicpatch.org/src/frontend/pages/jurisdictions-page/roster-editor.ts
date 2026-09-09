
import { html, nothing } from "lit-html";
import { component, useState, useEffect } from "haunted";
import "../../components/review/review-modal.js";
import "./jurisdiction-page.css";
import {
  patchPeopleData,
  generatePersonId,
} from "../../api.js";
import { fetchPeopleAssertions } from "../../api.js";
import { usePeopleState } from "../../components/edit-people/hooks/use-people-state.js";
import { emptyPerson } from "../../components/edit-people/people-editing.js";
import { blockingErrors, buildPersonCards, type PersonCard } from "../../components/people/person-cards.js";
import { personEditorPropsFor } from "../../components/person-editor/editor-props.js";
import { EMPTY_FROZEN } from "../review-session-page/frozen-fields.js";
import { renderRosterCards } from "./roster-section.js";
import { useJurisdictionPosts } from "../../hooks/use-jurisdiction-posts.js";
import { useJurisdictionRoles } from "../../hooks/use-jurisdiction-roles.js";
import "../../components/posts-list/post-add.js";

interface RosterEditorProps {
  people: any[];
  jurisdictionOcdid: string;
  canEdit: boolean;
  isLoading: boolean;
  blockedReason: string | null;
  onPublished: () => void;
}

interface OpenPerson {
  id: string;
  field: string | null;
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
  isLoading,
  blockedReason,
  onPublished,
}: RosterEditorProps) {
  const { posts, reload: reloadPosts } = useJurisdictionPosts(jurisdictionOcdid);
  const roles = useJurisdictionRoles();
  const [addingPostFor, setAddingPostFor] = useState<string | null>(null);
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
    handleResetAll,
  } = state;
  const [openPerson, setOpenPerson] = useState<OpenPerson | null>(null);
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
  const handlePersonSave = (id: string, updates: Record<string, unknown>) =>
    updatePerson(id, updates);
  const handleAdd = async () => {
    const personId = await generatePersonId();
    addPerson(emptyPerson(personId, jurisdictionOcdid));
    setOpenPerson({ id: personId, field: null });
  };
  const handlePublish = async () => {
    setPublishStage("publishing");
    setPublishError(null);
    try {
      await patchPeopleData(jurisdictionOcdid, peoplePatch);
      onPublished();
    } catch (err: any) {
      setPublishError(err.message ?? "Failed to publish.");
      setPublishStage("idle");
    }
  };
  const editorFor = (card: PersonCard) =>
    personEditorPropsFor(card, {
      frozen: EMPTY_FROZEN,
      dirtyIds,
      isReadOnly: !canEdit,
      jurisdictionOcdid,
      posts,
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
      onAddPost: setAddingPostFor,
      onRemovePerson: (id: string) => handleRemove([id]),
      onUnremovePerson: handleUnremove,
      onRestorePerson: handleRestore,
      onResetPerson: (id: string) => updatePerson(id, published.find((p) => p.id === id) ?? {}),
      cards: [],
      candidatesOpenFor: false,
      onToggleCandidates: () => {},
      onPickPartner: () => {},
    });
  const actions = canEdit
    ? html`
        <button class="btn-quiet" ?disabled=${isPublishing} @click=${handleAdd}>
          <i class="fa-solid fa-plus"></i> Add
        </button>
        ${dirty
          ? html`
              <button class="btn-quiet" ?disabled=${isPublishing} @click=${handleResetAll}>Discard</button>
              <button
                class="btn-primary"
                ?disabled=${isPublishing || blockers.length > 0}
                title=${blockers.length ? blockerTitle : ""}
                @click=${handlePublish}
              >
                ${publishLabel(blockers.length, publishStage)}
              </button>
            `
          : nothing}
      `
    : nothing;
  const handlePostAdded = (e: CustomEvent) => {
    const postId = e.detail?.post_id;
    if (addingPostFor && postId) handlePersonSave(addingPostFor, { post_id: postId });
    setAddingPostFor(null);
    reloadPosts();
  };
  return html`
    ${addingPostFor
      ? html`<civ-post-add
          .jurisdictionOcdid=${jurisdictionOcdid ?? ""}
          .roles=${roles}
          @added=${handlePostAdded}
          @cancel=${() => setAddingPostFor(null)}
        ></civ-post-add>`
      : ""}
    ${renderRosterCards({
      cards,
      isLoading,
      blockedReason,
      actions,
      onOpenPerson: canEdit ? (id: string) => setOpenPerson({ id, field: null }) : null,
    })}
    ${publishError
      ? html`<p style="color: var(--diff-removed);">${publishError}</p>`
      : nothing}
    <review-modal
      .cards=${cards}
      .posts=${posts}
      .openPersonId=${openPerson?.id ?? null}
      .focusFieldKey=${openPerson?.field ?? null}
      .editor=${editorFor}
      .isReadOnly=${!canEdit}
      .onClose=${() => setOpenPerson(null)}
    ></review-modal>
  `;
}

customElements.define(
  "civ-roster-editor",
  component(RosterEditor as any, { useShadowDOM: false }),
);
