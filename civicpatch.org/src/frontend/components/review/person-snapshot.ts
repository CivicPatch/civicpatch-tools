// The modal's undo buffer (spec §6.1). Pure — the modal owns the state.
//
// Edits apply live, exactly as in Detail, so "Revert this person" needs a record
// of where the person stood when the modal opened. That is an undo buffer, not a
// draft: usePeopleState already is the draft layer, and nesting a second one
// gives two undo semantics with no way to tell them apart.
//
// It captures the departure flags as well as the field values. Restoring values
// while leaving a flag set produces an impossible state — a person marked
// restored with no record, or dropped while reading as unchanged (§12's
// invariant: published iff they have a record and are not deleted).

import { type DiffRecord } from "../people-diff/diff-model.js";

export interface PersonSnapshot {
  personId: string;
  record: DiffRecord;
  isDeleted: boolean;
  isRestored: boolean;
}

export function takeSnapshot(
  personId: string,
  record: DiffRecord,
  deletedIds: Set<string>,
  restoredIds: Set<string>,
): PersonSnapshot {
  return {
    personId,
    // Copied, not referenced: the live record is mutated by every keystroke, so
    // holding it would make the snapshot track the edits it exists to undo.
    record: record ? { ...record } : record,
    isDeleted: deletedIds.has(personId),
    isRestored: restoredIds.has(personId),
  };
}

// What has to happen to put the person back. Split from the doing so the rules
// are testable without a DOM: the caller runs whichever of these came back true.
export interface RevertPlan {
  updates: Record<string, unknown> | null;
  delete: boolean;
  undelete: boolean;
  restore: boolean;
  undoRestore: boolean;
}

export function planRevert(
  snapshot: PersonSnapshot,
  deletedIds: Set<string>,
  restoredIds: Set<string>,
): RevertPlan {
  const isDeleted = deletedIds.has(snapshot.personId);
  const isRestored = restoredIds.has(snapshot.personId);
  return {
    // usePeopleState merges shallowly, so handing back the whole snapshot record
    // restores every field the reviewer touched in one write.
    updates: snapshot.record ? { ...snapshot.record } : null,
    delete: snapshot.isDeleted && !isDeleted,
    undelete: !snapshot.isDeleted && isDeleted,
    restore: snapshot.isRestored && !isRestored,
    undoRestore: !snapshot.isRestored && isRestored,
  };
}

// Nothing to undo — used to disable Revert rather than offering a no-op.
export function isUnchangedSince(
  snapshot: PersonSnapshot,
  record: DiffRecord,
  deletedIds: Set<string>,
  restoredIds: Set<string>,
): boolean {
  return (
    JSON.stringify(record ?? null) === JSON.stringify(snapshot.record ?? null) &&
    deletedIds.has(snapshot.personId) === snapshot.isDeleted &&
    restoredIds.has(snapshot.personId) === snapshot.isRestored
  );
}
