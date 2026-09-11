import { useEffect } from "haunted";
import { adjacentPeer, type PersonCard } from "../components/people/person-cards.js";
import { altArrowDirection, isTyping } from "../utils/keyboard.js";

// Alt+Left/Right steps to the previous/next peer while one card is open — shared by every
// modal that opens one PersonCard at a time out of a list (review session, roster editor).
// `onNavigate` is deliberately not a dependency: callers pass a fresh closure each render
// that only ever calls their own stable state setters, so using whichever closure was
// current when the listener last attached is equivalent to using the latest one.
export function useAltArrowPeerNav(
  openId: string | null,
  peers: PersonCard[],
  onNavigate: (next: PersonCard) => void,
) {
  useEffect(() => {
    if (!openId) return;
    const onKey = (e: KeyboardEvent) => {
      const direction = altArrowDirection(e);
      if (!direction || isTyping(document.activeElement)) return;
      const nextCard = adjacentPeer(peers, openId, direction);
      if (!nextCard) return;
      e.preventDefault();
      onNavigate(nextCard);
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [openId, peers]);
}
