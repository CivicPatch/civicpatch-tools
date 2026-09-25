export const isTyping = (el: Element | null): boolean =>
  !!el && /^(input|textarea|select)$/i.test(el.tagName);
