// Building one person's rail props, in one place.
//
// Detail renders a list of rails and the modal renders exactly one, and they
// must agree about what a person's row is — the modal is the rail mounted with a
// one-person list, not a second editor (§6). Extracted here so neither has to
// reproduce the other's rules.

import { visibleFields, type FrozenFields } from "../../pages/review-session-page/frozen-fields.js";
import { type Save } from "../review/field-controls.js";
import { RailStatus, type ReviewCard } from "../review/review-cards.js";
import { type LinkCandidate, type PersonRailProps } from "./person-rail.js";

export interface RailContext {
  frozen: FrozenFields;
  dirtyIds: Set<string>;
  isReadOnly: boolean;
  jurisdictionOcdid: string | null | undefined;
  linkCandidates: LinkCandidate[];
  expandedIds: Set<string>;
  onToggleExpand: (personId: string) => void;
  onPersonSave: (id: string, updates: Record<string, unknown>) => void;
  onRemovePerson: (id: string) => void;
  onUnremovePerson: (id: string) => void;
  onRestorePerson: (person: any) => void;
  onResetPerson: (id: string) => void;
  // "These two records are one person." Link is this with the merge defaults
  // untouched; the picker is this with a plan the reviewer edited.
  onCombine: (survivorId: string, absorbedId: string) => void;
}

// Only people the scrape didn't find. Someone the *reviewer* dropped carries
// status DELETED rather than REMOVED, so they are already excluded here — which
// matters, because merging adopts the target's id, and a target the reviewer
// removed would hand the survivor an id already marked for removal.
export function linkCandidatesFrom(cards: ReviewCard[]): LinkCandidate[] {
  return cards
    .filter((card) => card.status === RailStatus.REMOVED)
    .map((card) => ({
      id: card.personId,
      name: card.oldRecord?.name || "(unnamed)",
      office: card.oldRecord?.office?.name ?? "",
    }));
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
    linkCandidates: ctx.linkCandidates,
    // The target is the record already in the database, so it survives and keeps
    // its id — which is what linking always did, now by the shared survivor rule.
    onLink: (target: any) => ctx.onCombine(target.id, card.personId),
  };
}
