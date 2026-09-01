import { useState, useEffect } from "haunted";
import {
  nextFrozen,
  INITIAL_FROZEN_STATE,
  type CardFields,
  type FrozenFields,
  type FrozenState,
} from "./frozen-fields.js";

// Owns the frozen visible-field set for the card under review (§2.1).
//
// It lives on the page, not in a view: Overview, Detail and the modal must agree
// on which fields a person shows, and switching between them must not recompute
// the set. Preview is excluded by not asking — it renders the published result,
// so it has no collapsed set to freeze.
//
// All the rules are in nextFrozen, which is pure and unit-tested. This is only
// the state: derive during render so a field that surfaces is visible on the
// same frame, then persist. nextFrozen returns the same reference when nothing
// changed, so the effect's dependency is stable and it cannot loop.
export function useFrozenFields(
  changesetId: string | null,
  cards: CardFields[],
): FrozenFields {
  const [state, setState] = useState<FrozenState>(INITIAL_FROZEN_STATE);

  const next = nextFrozen(state, changesetId, cards);

  useEffect(() => {
    if (next !== state) setState(next);
  }, [next]);

  return next.frozen;
}
