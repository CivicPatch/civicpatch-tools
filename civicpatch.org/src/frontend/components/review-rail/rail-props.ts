// Building one person's rail props, in one place.
//
// Detail renders a list of rails and the modal renders exactly one, and they
// must agree about what a person's row is — the modal is the rail mounted with a
// one-person list, not a second editor (§6). Extracted here so neither has to
// reproduce the other's rules.

import { visibleFields, type FrozenFields } from "../../pages/review-session-page/frozen-fields.js";
import { type Save } from "../review/field-controls.js";
import { RailStatus, type ReviewCard } from "../review/review-cards.js";
import { canMerge, mergeCandidates } from "../review/merge-model.js";
import { type PersonRailProps } from "./person-rail.js";

export interface RailContext {
  frozen: FrozenFields;
  dirtyIds: Set<string>;
  isReadOnly: boolean;
  jurisdictionOcdid: string | null | undefined;
  expandedIds: Set<string>;
  onToggleExpand: (personId: string) => void;
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
  onRemovePerson: (id: string) => void;
  onUnremovePerson: (id: string) => void;
  onRestorePerson: (person: any) => void;
  onResetPerson: (id: string) => void;
  // Step 1 of a merge, in place on the rail: which person's strip is open, and
  // what to do when one of its candidates is picked.
  cards: ReviewCard[];
  mergeOpenId: string | null;
  onToggleMerge: (personId: string) => void;
  onPickPartner: (anchorId: string, partnerId: string) => void;
}


export function railPropsFor(card: ReviewCard, ctx: RailContext): PersonRailProps {
  const save: Save = (updates) => ctx.onPersonSave(card.personId, updates);
  return {
    status: card.status,
    oldRecord: card.oldRecord,
    newRecord: card.newRecord,
    surviving: card.surviving,
    frozenReasons: visibleFields(ctx.frozen, card.personId),
    issues: card.issues,
    isReadOnly: ctx.isReadOnly,
    jurisdictionOcdid: ctx.jurisdictionOcdid,
    isDirty: ctx.dirtyIds.has(card.personId),
    isExpanded: ctx.expandedIds.has(card.personId),
    onToggleExpand: () => ctx.onToggleExpand(card.personId),
    onSave: save,
    onRemove: () => ctx.onRemovePerson(card.personId),
    onUnremove: () => ctx.onUnremovePerson(card.personId),
    // Rebuilding the record needs the old side, which only the card has.
    onRestore: () => ctx.onRestorePerson(card.oldRecord),
    // Reset is offered only to someone with edits to discard. A card the
    // reviewer has not touched has nothing to reset to.
    onReset:
      ctx.dirtyIds.has(card.personId) && card.status !== RailStatus.REMOVED
        ? () => ctx.onResetPerson(card.personId)
        : null,
    mergeCandidates: canMerge(card) ? mergeCandidates(card, ctx.cards) : [],
    isMergeOpen: ctx.mergeOpenId === card.personId,
    onToggleMerge: () => ctx.onToggleMerge(card.personId),
    onPickPartner: (partnerId: string) => ctx.onPickPartner(card.personId, partnerId),
  };
}
