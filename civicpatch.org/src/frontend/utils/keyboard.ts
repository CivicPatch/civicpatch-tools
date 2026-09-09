export const isTyping = (el: Element | null): boolean =>
  !!el && /^(input|textarea|select)$/i.test(el.tagName);

export function altArrowDirection(e: KeyboardEvent): -1 | 1 | 0 {
  if (!e.altKey) return 0;
  if (e.key === "ArrowLeft") return -1;
  if (e.key === "ArrowRight") return 1;
  return 0;
}
