// Detail v2 — the list of rails (spec §5).
//
// Ungrouped: one list in slot order. Unlike Overview, this is a surface you work
// top to bottom, so To Review / Unchanged headings would only add scrolling.
//
// The frozen field set is a prop, not state. Three views have to agree on which
// fields a person shows and switching between them must not recompute the set
// (§2.1), so the review-session page owns it.

import { html, nothing } from "lit-html";
import { component, useState } from "haunted";
import "./review-rail.css";
import { type FrozenFields, visibleFields } from "../../pages/review-session-page/frozen-fields.js";
import { type Save } from "../people-diff/field-controls.js";
import { renderPersonRail } from "./person-rail.js";
import { RailStatus, type ReviewCard } from "../review/review-cards.js";
import { buildLinkUpdates } from "../people-diff/diff-model.js";

interface ReviewRailListProps {
  cards: ReviewCard[];
  frozen: FrozenFields;
  // Expansion is per card, so it resets when the reviewer moves on. §21.4 also
  // wants it invalidated by identity-changing actions — that lands with merge.
  requestId: string | null;
  dirtyIds: Set<string>;
  isReadOnly: boolean;
  jurisdictionOcdid: string | null | undefined;
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
  onDeletePerson: (id: string) => void;
  onUndeletePerson: (id: string) => void;
  onRestorePerson: (person: any) => void;
  onResetPerson: (id: string) => void;
  onAdd?: () => void;
}

const NO_EXPANSION = { requestId: null as string | null, ids: new Set<string>() };

function ReviewRailList({
  cards,
  frozen,
  requestId,
  dirtyIds,
  isReadOnly,
  jurisdictionOcdid,
  onPersonSave,
  onDeletePerson,
  onUndeletePerson,
  onRestorePerson,
  onResetPerson,
  onAdd,
}: ReviewRailListProps) {
  const [expansion, setExpansion] = useState(NO_EXPANSION);

  // Advancing to the next card is a new card load, and this element is not
  // remounted between them — so the id it was opened for has to be checked
  // rather than assumed, or expansion leaks from one reviewer's card to the next.
  const expandedIds = expansion.requestId === requestId ? expansion.ids : NO_EXPANSION.ids;

  // Only people the scrape didn't find. Someone the *reviewer* dropped carries
  // status DELETED rather than REMOVED, so they are already excluded here — which
  // matters, because linking adopts the target's id and a deleted target would
  // hand the added person an id already marked for deletion (§21).
  const linkCandidates = cards
    .filter((card) => card.status === RailStatus.REMOVED)
    .map((card) => ({
      id: card.personId,
      name: card.oldRecord?.name || "(unnamed)",
      office: card.oldRecord?.office?.name ?? "",
    }));

  const toggleExpand = (personId: string) => {
    const ids = new Set(expandedIds);
    if (ids.has(personId)) ids.delete(personId);
    else ids.add(personId);
    setExpansion({ requestId, ids });
  };

  if (!cards.length) {
    return html`<div class="review-rail-list">
      <p class="review-rail__empty">No people to review.</p>
    </div>`;
  }

  return html`
    <div class="review-rail-list">
      ${cards.map((card) => {
        const save: Save = (updates) => onPersonSave(card.personId, updates);
        return renderPersonRail({
          status: card.status,
          oldRecord: card.oldRecord,
          newRecord: card.newRecord,
          surviving: card.surviving,
          frozenReasons: visibleFields(frozen, card.personId),
          issues: card.issues,
          isReadOnly,
          jurisdictionOcdid,
          isDirty: dirtyIds.has(card.personId),
          isExpanded: expandedIds.has(card.personId),
          onToggleExpand: () => toggleExpand(card.personId),
          onSave: save,
          onDelete: () => onDeletePerson(card.personId),
          onUndelete: () => onUndeletePerson(card.personId),
          // Rebuilding the record needs the old side, which only the card has.
          onRestore: () => onRestorePerson(card.oldRecord),
          // Reset is offered only to someone with edits to discard. A card the
          // reviewer has not touched has nothing to reset to.
          onReset:
            dirtyIds.has(card.personId) && card.status !== RailStatus.REMOVED
              ? () => onResetPerson(card.personId)
              : null,
          linkCandidates,
          onLink: (target: any) =>
            onPersonSave(card.personId, buildLinkUpdates(card.newRecord, target)),
        });
      })}
      ${!isReadOnly && onAdd
        ? html`<button class="review-rail review-rail--ghost" @click=${onAdd}>
            <span class="review-rail__ghost-mark">+</span>
            <span class="review-rail__ghost-label">Add a person the scrape missed</span>
          </button>`
        : nothing}
    </div>
  `;
}

customElements.define(
  "review-rail-list",
  component(ReviewRailList as unknown as () => unknown, { useShadowDOM: false }),
);