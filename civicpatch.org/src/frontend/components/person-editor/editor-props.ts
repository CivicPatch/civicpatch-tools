// Building one person's editor props, in one place.
//
// Detail renders a list of editors and the modal renders exactly one, and they
// must agree about what a person's row is — the modal is the editor mounted with a
// one-person list, not a second one (§6). Extracted here so neither has to
// reproduce the other's rules.

import { visibleFields, type FrozenFields } from "../../pages/review-session-page/frozen-fields.js";
import { type Save } from "../review/field-controls.js";
import { PersonStatus, type ReviewCard } from "../review/review-cards.js";
import { canMerge, mergeCandidates } from "../review/merge-model.js";
import { type PersonEditorProps } from "./person-editor.js";

export interface EditorContext {
  frozen: FrozenFields;
  dirtyIds: Set<string>;
  isReadOnly: boolean;
  jurisdictionOcdid: string | null | undefined;
  // A predicate, not a set: a page whose default is "expanded" has no set to
  // keep in sync with the roster, so a person it has never seen cannot arrive
  // collapsed.
  isExpanded: (personId: string) => boolean;
  onToggleExpand: (personId: string) => void;
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
  onRemovePerson: (id: string) => void;
  onUnremovePerson: (id: string) => void;
  onRestorePerson: (person: any) => void;
  onResetPerson: (id: string) => void;
  // Step 1 of a merge, in place on the editor: which person's strip is open, and
  // what to do when one of its candidates is picked.
  cards: ReviewCard[];
  mergeOpenId: string | null;
  onToggleMerge: (personId: string) => void;
  onPickPartner: (anchorId: string, partnerId: string) => void;
}


export function personEditorPropsFor(card: ReviewCard, ctx: EditorContext): PersonEditorProps {
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
    isExpanded: ctx.isExpanded(card.personId),
    onToggleExpand: () => ctx.onToggleExpand(card.personId),
    onSave: save,
    onRemove: () => ctx.onRemovePerson(card.personId),
    onUnremove: () => ctx.onUnremovePerson(card.personId),
    // Rebuilding the record needs the old side, which only the card has.
    onRestore: () => ctx.onRestorePerson(card.oldRecord),
    // Reset is offered only to someone with edits to discard. A card the
    // reviewer has not touched has nothing to reset to.
    onReset:
      ctx.dirtyIds.has(card.personId) && card.status !== PersonStatus.REMOVED
        ? () => ctx.onResetPerson(card.personId)
        : null,
    // Only the modal opens on a field; it sets this over the props it is handed.
    focusField: null,
    mergeCandidates: canMerge(card) ? mergeCandidates(card, ctx.cards) : [],
    isMergeOpen: ctx.mergeOpenId === card.personId,
    onToggleMerge: () => ctx.onToggleMerge(card.personId),
    onPickPartner: (partnerId: string) => ctx.onPickPartner(card.personId, partnerId),
  };
}
