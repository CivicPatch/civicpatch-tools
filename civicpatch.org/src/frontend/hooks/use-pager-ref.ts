import { useMemo } from "haunted";
import { createRef } from "lit/directives/ref.js";
import { scrollListTop } from "../utils/scroll-list-top.js";

// One ref per paginated list, plus the scroll call Next/Previous should trigger alongside
// setPage — otherwise the reader is left wherever they clicked from (most often the bottom
// pager) instead of at the top of the page that just loaded.
export function usePagerRef<T extends HTMLElement = HTMLElement>() {
  const listRef = useMemo(() => createRef<T>(), []);
  const scrollToTop = () => scrollListTop(listRef.value);
  return { listRef, scrollToTop };
}
