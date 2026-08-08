// The frozen visible-field set (spec §2.1). Pure — the hook that owns the state
// lives in use-frozen-fields.ts.
//
// A card's visible fields are computed when it loads and then only ever GROW.
// Both halves matter and they are asymmetric on purpose:
//
//   - Fields never leave, because a row vanishing under the reviewer is the
//     thing freezing exists to prevent.
//   - Fields may join, because `fieldError` reads across fields: end_date's
//     term-order check reads start_date, so editing a *visible* field can raise
//     a blocking error on a *hidden* one. Frozen strictly, publish would fail
//     with no row on screen to fix.
//
// Growth has to be remembered rather than recomputed. If the set were
// `frozen ∪ {fields erroring right now}`, then fixing the error would drop the
// field out and the row would vanish at the exact moment the reviewer fixed it —
// and §2.2 wants it to stay and switch its badge to `resolved`. The question is
// "has this field ever surfaced on this card?", which current records cannot
// answer.
//
// Both invariants are properties of the structure, not rules to remember:
// nothing is ever deleted, and an entry is only inserted if absent — so the
// reason a field FIRST appeared is the one that sticks (§2.2), while its badge
// is derived from current state.

import { type FieldReason, type SurvivingField } from "../../components/fields/field-model.js";

// person id -> field key -> why that field first became visible
export type FrozenFields = Map<string, Map<string, FieldReason>>;

export interface CardFields {
  personId: string;
  surviving: SurvivingField[];
}

export const EMPTY_FROZEN: FrozenFields = new Map();

// Insert-if-absent, never delete. Returns the *same reference* when nothing new
// appeared, so callers can use identity to decide whether to persist — which is
// what keeps the owning hook from looping.
export function foldVisible(
  frozen: FrozenFields,
  cards: CardFields[],
): FrozenFields {
  let next: FrozenFields | null = null;

  for (const { personId, surviving } of cards) {
    const current = frozen.get(personId);
    let personNext: Map<string, FieldReason> | null = null;

    for (const { field, reason } of surviving) {
      if (current?.has(field.key)) continue;
      if (!personNext) personNext = new Map(current ?? []);
      if (personNext.has(field.key)) continue;
      personNext.set(field.key, reason);
    }

    if (!personNext) continue;
    if (!next) next = new Map(frozen);
    next.set(personId, personNext);
  }

  return next ?? frozen;
}

// A person who left the card takes their frozen set with them. A merge collapses
// two rows into one, and without this the absorbed id keeps an entry that would
// resurrect — with the wrong reasons — if that id ever came back. Same reference
// when nothing was stale, preserving foldVisible's convention.
export function pruneToLiving(
  frozen: FrozenFields,
  livingIds: Set<string>,
): FrozenFields {
  let next: FrozenFields | null = null;
  for (const personId of frozen.keys()) {
    if (livingIds.has(personId)) continue;
    if (!next) next = new Map(frozen);
    next.delete(personId);
  }
  return next ?? frozen;
}

export interface FrozenState {
  requestId: string | null;
  frozen: FrozenFields;
}

export const INITIAL_FROZEN_STATE: FrozenState = {
  requestId: null,
  frozen: EMPTY_FROZEN,
};

// One card's worth of freezing, as a transition. Advancing to the next card is
// a new load, so a different request_id starts from empty.
//
// There is no separate "wait for the people to arrive" step, and there doesn't
// need to be: `useReviewPeople` resolves matches asynchronously, so the first
// render of a card has no people — but seeding from an empty list and then
// folding when they arrive gives exactly the same map as seeding from them
// directly, because folding is insert-only. The async gap costs nothing.
//
// Returns the same reference when nothing changed, so the caller can persist on
// identity instead of deep-comparing.
export function nextFrozen(
  previous: FrozenState,
  requestId: string | null,
  cards: CardFields[],
): FrozenState {
  const sameCard = previous.requestId === requestId;
  const carried = sameCard ? previous.frozen : EMPTY_FROZEN;
  // An empty list means the people have not arrived yet, not that everyone left,
  // so pruning waits for a populated one. A merge always leaves a survivor, so
  // it can never legitimately empty the card.
  const living = cards.length
    ? pruneToLiving(carried, new Set(cards.map((card) => card.personId)))
    : carried;
  const frozen = foldVisible(living, cards);
  if (sameCard && frozen === previous.frozen) return previous;
  return { requestId, frozen };
}

export function visibleFields(
  frozen: FrozenFields,
  personId: string,
): Map<string, FieldReason> {
  return frozen.get(personId) ?? new Map();
}

export function isFieldVisible(
  frozen: FrozenFields,
  personId: string,
  fieldKey: string,
): boolean {
  return frozen.get(personId)?.has(fieldKey) ?? false;
}

// Fields in the schema order they were frozen in, for rendering. Reads the
// person's frozen map rather than recomputing, so the order is stable even as
// values change underneath.
export function frozenFieldKeys(
  frozen: FrozenFields,
  personId: string,
): string[] {
  return [...visibleFields(frozen, personId).keys()];
}
