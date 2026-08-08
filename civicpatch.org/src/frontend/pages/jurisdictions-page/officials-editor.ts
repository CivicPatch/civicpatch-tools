// The published roster, edited in place.
//
// Not a second editor: the cards are the ones Overview and Preview draw, and
// clicking one opens the same review modal the review flow opens. What differs is
// the baseline — there is no scrape proposal here, so `existing` and
// `currentPeople` start identical and every card is UNCHANGED until someone edits.
//
// Publishing reuses the manual-edit path: a people patch becomes a PR, which is
// merged immediately.

import { html, nothing } from "lit-html";
import { component, useState, useEffect } from "haunted";
import "../../components/review/review-modal.js";
import "./jurisdiction-page.css";
import {
  patchPeopleData,
  saveAndEnqueueMerge,
  pollMergeStatus,
  generatePersonId,
} from "../../api.js";
import { usePeopleState } from "../../components/edit-people/hooks/use-people-state.js";
import { emptyPerson } from "../../components/edit-people/people-editing.js";
import { blockingErrors, buildReviewCards, type ReviewCard } from "../../components/review/review-cards.js";
import { personEditorPropsFor } from "../../components/person-editor/editor-props.js";
import { EMPTY_FROZEN } from "../review-session-page/frozen-fields.js";
import { renderOfficialsCards } from "./officials-section.js";

interface OfficialsEditorProps {
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

type PublishStage = "idle" | "opening" | "merging";

// Blockers outrank the stage copy: a card with errors never reaches "Opening PR…".
function publishLabel(blockerCount: number, stage: PublishStage): string {
  if (blockerCount) return `${blockerCount} to fix before publishing`;
  if (stage === "opening") return "Opening PR…";
  if (stage === "merging") return "Publishing…";
  return "Publish changes";
}

function OfficialsEditor({
  people,
  jurisdictionOcdid,
  canEdit,
  isLoading,
  blockedReason,
  onPublished,
}: OfficialsEditorProps) {
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
  // Collapsed, not expanded: nothing here is ever a diff, so expanded is the default.
  const [collapsedIds, setCollapsedIds] = useState<Set<string>>(new Set());
  // The write is a PR: the endpoint returns once it is *enqueued*, then Temporal
  // merges it and syncs open-data back into the DB. Reloading on enqueue lands on
  // stale data and reads as "nothing happened", so the button says which half it
  // is in and only reloads once the merge has actually settled.
  const [publishStage, setPublishStage] = useState<PublishStage>("idle");
  const [publishError, setPublishError] = useState<string | null>(null);
  const isPublishing = publishStage !== "idle";

  // People arrive async, so the baseline is set when they land — not at mount.
  useEffect(() => {
    assignPeople(published);
  }, [people]);

  const cards: ReviewCard[] = buildReviewCards({
    existing: published,
    currentPeople: currentPeople ?? [],
    removedIds,
    restoredIds,
    issues: [],
  });

  // The same rule the review session publishes by, so the two pages cannot
  // disagree about whether a roster is publishable (§9). The per-field badges are
  // already on screen; this is what stops the button.
  const blockers = blockingErrors(cards);
  const blockerTitle = blockers
    .map((blocker) => `${blocker.name} — ${blocker.fieldLabel}: ${blocker.message}`)
    .join("\n");

  const handlePersonSave = (id: string, updates: Record<string, unknown>) =>
    updatePerson(id, updates);

  const handleAdd = async () => {
    const personId = await generatePersonId();
    addPerson(emptyPerson(personId, jurisdictionOcdid));
    setOpenPerson({ id: personId, field: null });
  };

  const handlePublish = async () => {
    setPublishStage("opening");
    setPublishError(null);
    try {
      const { data } = await patchPeopleData(jurisdictionOcdid, peoplePatch);
      await saveAndEnqueueMerge(data.pr_number, data.request_id, jurisdictionOcdid, null);
      setPublishStage("merging");
      // Merging also syncs open-data back into the DB (publish_side_effects), so
      // by the time this resolves a reload shows the published values.
      await pollMergeStatus(data.pr_number);
      onPublished();
    } catch (err: any) {
      setPublishError(err.message ?? "Failed to publish.");
      setPublishStage("idle");
    }
  };

  // No scrape diff here, so nothing is frozen and there is no merge picker: both
  // exist to reconcile a proposal against the published record.
  const editorFor = (card: ReviewCard) =>
    personEditorPropsFor(card, {
      frozen: EMPTY_FROZEN,
      dirtyIds,
      isReadOnly: !canEdit,
      jurisdictionOcdid,
      isExpanded: (id: string) => !collapsedIds.has(id),
      onToggleExpand: () => {
        const next = new Set(collapsedIds);
        next.has(card.personId) ? next.delete(card.personId) : next.add(card.personId);
        setCollapsedIds(next);
      },
      onPersonSave: handlePersonSave,
      // handleRemove takes a list; passing an id raw spreads it into characters.
      onRemovePerson: (id: string) => handleRemove([id]),
      onUnremovePerson: handleUnremove,
      onRestorePerson: handleRestore,
      onResetPerson: (id: string) => updatePerson(id, published.find((p) => p.id === id) ?? {}),
      // No merge here yet. The editor hides the button when there are no candidates,
      // and an empty list is how that is said — better than rendering a control
      // whose handler does nothing.
      cards: [],
      mergeOpenId: null,
      onToggleMerge: () => {},
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

  return html`
    ${renderOfficialsCards({
      cards,
      isLoading,
      blockedReason,
      actions,
      onOpenPerson: canEdit ? (id: string) => setOpenPerson({ id, field: null }) : null,
    })}

    ${publishError
      ? html`<p style="color: var(--pico-del-color);">${publishError}</p>`
      : nothing}

    <review-modal
      .cards=${cards}
      .openPersonId=${openPerson?.id ?? null}
      .focusFieldKey=${openPerson?.field ?? null}
      .editor=${editorFor}
      .isReadOnly=${!canEdit}
      .onClose=${() => setOpenPerson(null)}
    ></review-modal>
  `;
}

customElements.define(
  "civ-officials-editor",
  component(OfficialsEditor as any, { useShadowDOM: false }),
);
