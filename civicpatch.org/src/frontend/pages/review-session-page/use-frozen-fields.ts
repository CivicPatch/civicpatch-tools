import { useState, useEffect } from "haunted";
import {
  nextFrozen,
  INITIAL_FROZEN_STATE,
  type CardFields,
  type FrozenFields,
  type FrozenState,
} from "../../components/person-editor/frozen-fields.js";

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
